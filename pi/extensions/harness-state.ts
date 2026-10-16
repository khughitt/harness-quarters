import { spawn } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

export default function harnessState(pi: ExtensionAPI) {
  let running: Promise<void> | undefined;
  let pending = false;
  let shuttingDown = false;
  let warned = false;

  function warn(ctx: ExtensionContext, message: string) {
    if (warned) return;
    warned = true;
    ctx.ui.notify(`Harness state refresh failed: ${message}`, "warning");
  }

  function refresh(ctx: ExtensionContext): Promise<void> {
    return new Promise<void>((resolve) => {
      const command = process.env.HQ_HARNESS_STATE_REFRESH ?? join(homedir(), ".local/bin/harness-state-refresh");
      const child = spawn(command, [], { detached: true, stdio: "pipe" });
      let output = "";
      let terminating = false;
      let finished = false;
      let killTimer: ReturnType<typeof setTimeout> | undefined;
      const finish = (failure?: string) => {
        if (finished) return;
        finished = true;
        process.off("exit", onExit);
        clearTimeout(timer);
        if (killTimer) clearTimeout(killTimer);
        if (failure) warn(ctx, failure);
        resolve();
      };
      const killGroup = (signal: NodeJS.Signals) => {
        try {
          if (child.pid) process.kill(-child.pid, signal);
        } catch (error) {
          if ((error as NodeJS.ErrnoException).code !== "ESRCH") warn(ctx, String(error));
        }
      };
      const onExit = () => killGroup("SIGKILL");
      process.on("exit", onExit);
      const terminate = (failure: string) => {
        clearTimeout(timer);
        terminating = true;
        killGroup("SIGTERM");
        // A closed leader does not establish that its process group has finished.
        killTimer = setTimeout(() => {
          killGroup("SIGKILL");
          finish(failure);
        }, 1_000);
      };
      const timer = setTimeout(() => terminate("timed out after 10 seconds"), 10_000);
      child.stdout.on("data", (data) => { output += data; });
      child.stderr.on("data", (data) => { output += data; });
      child.on("error", (error) => finish(error.message));
      child.on("close", (code, signal) => {
        if (terminating) return;
        const failure = code === 0 ? undefined : `exit ${code ?? signal}: ${output.trim()}`;
        try {
          if (child.pid) {
            process.kill(-child.pid, 0);
            terminate(failure ?? "refresh exited with running descendants");
            return;
          }
        } catch (error) {
          if ((error as NodeJS.ErrnoException).code !== "ESRCH") {
            terminate(failure ?? String(error));
            return;
          }
        }
        finish(failure);
      });
      child.stdin.on("error", () => {}); // A child that exits early can close stdin before end().
      child.stdin.end("");
    }).catch((error) => { warn(ctx, String(error)); });
  }

  function request(ctx: ExtensionContext) {
    if (shuttingDown) return;
    if (running) {
      pending = true;
      return;
    }
    running = (async () => {
      do {
        pending = false;
        await refresh(ctx);
      } while (pending && !shuttingDown);
    })().finally(() => { running = undefined; });
  }

  for (const event of ["model_select", "thinking_level_select"] as const) {
    pi.on(event, async (_event, ctx) => {
      await new Promise<void>((resolve) => setImmediate(resolve));
      request(ctx);
    });
  }
  pi.on("agent_settled", (_event, ctx) => { request(ctx); });
  pi.on("session_shutdown", async (_event, ctx) => {
    shuttingDown = true;
    pending = false;
    await running;
    await refresh(ctx);
  });
}
