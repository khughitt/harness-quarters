# Codex SSH Profiles

**Date:** 2026-07-07

**Status:** Reference

## Purpose

Use separate personal and work Codex setups while keeping `~/.ssh` unreadable to Codex. Codex should
authenticate to GitHub through SSH agent sockets, not by reading private keys.

This avoids the current Codex sandbox issue where `/etc/ssh/ssh_config.d` can appear owned by
`nobody:nobody`, which makes OpenSSH reject system SSH config files.

## Layout

```text
~/.codex/
  config.toml              # personal Codex config

~/.codex-work/
  config.toml              # work Codex config

~/.config/codex/ssh-personal/
  config
  known_hosts

~/.config/codex/ssh-work/
  config
  known_hosts
```

Do not copy private keys into `~/.config/codex`. Keep private keys in `~/.ssh` and load them into the
appropriate agent outside Codex.

## Codex Config

Personal `~/.codex/config.toml` should include:

```toml
[permissions.workspace-local.filesystem]
":minimal" = "read"
":tmpdir" = "write"
":slash_tmp" = "write"

"~/.nvm/versions/node" = "read"
"~/.config/codex/ssh-personal" = "read"
"/run/user/1000/codex-personal-ssh-agent.sock" = "read"

"~/.ssh" = "deny"
"~/.gnupg" = "deny"
```

Work `~/.codex-work/config.toml` should use the work equivalents:

```toml
[permissions.workspace-local.filesystem]
":minimal" = "read"
":tmpdir" = "write"
":slash_tmp" = "write"

"~/.nvm/versions/node" = "read"
"~/.config/codex/ssh-work" = "read"
"/run/user/1000/codex-work-ssh-agent.sock" = "read"

"~/.ssh" = "deny"
"~/.gnupg" = "deny"
```

Keep the usual workspace roots, cache paths, network config, project trust entries, and MCP settings
in each config as needed.

## SSH Config

Personal `~/.config/codex/ssh-personal/config`:

```sshconfig
Host github.com
  HostName github.com
  User git
  IdentitiesOnly yes
  IdentityAgent /run/user/1000/codex-personal-ssh-agent.sock
  UserKnownHostsFile ~/.config/codex/ssh-personal/known_hosts
```

Work `~/.config/codex/ssh-work/config`:

```sshconfig
Host github-work
  HostName github.com
  User git
  IdentitiesOnly yes
  IdentityAgent /run/user/1000/codex-work-ssh-agent.sock
  UserKnownHostsFile ~/.config/codex/ssh-work/known_hosts
```

Populate known hosts outside Codex:

```bash
mkdir -p ~/.config/codex/ssh-personal ~/.config/codex/ssh-work
ssh-keyscan github.com > ~/.config/codex/ssh-personal/known_hosts
cp ~/.config/codex/ssh-personal/known_hosts ~/.config/codex/ssh-work/known_hosts
chmod 755 ~/.config/codex/ssh-personal ~/.config/codex/ssh-work
chmod 644 ~/.config/codex/ssh-personal/* ~/.config/codex/ssh-work/*
```

## SSH Agents

Start one agent per GitHub identity outside Codex:

```bash
ssh-agent -a /run/user/1000/codex-personal-ssh-agent.sock
SSH_AUTH_SOCK=/run/user/1000/codex-personal-ssh-agent.sock ssh-add ~/.ssh/id_rsa
SSH_AUTH_SOCK=/run/user/1000/codex-personal-ssh-agent.sock ssh-add -L
```

```bash
ssh-agent -a /run/user/1000/codex-work-ssh-agent.sock
SSH_AUTH_SOCK=/run/user/1000/codex-work-ssh-agent.sock ssh-add ~/.ssh/<work-private-key>
SSH_AUTH_SOCK=/run/user/1000/codex-work-ssh-agent.sock ssh-add -L
```

Each agent should list only the key for that account.

## Repo Git Config

Set `core.sshCommand` repo-locally. This avoids changing global Git behavior.

Personal repos:

```bash
git config core.sshCommand "ssh -F ~/.config/codex/ssh-personal/config"
git remote set-url origin git@github.com:<personal-owner>/<repo>.git
```

Work repos:

```bash
git config core.sshCommand "ssh -F ~/.config/codex/ssh-work/config"
git remote set-url origin git@github-work:<work-owner>/<repo>.git
```

## Launching Codex

Personal:

```bash
CODEX_HOME=$HOME/.codex codex
```

Work:

```bash
CODEX_HOME=$HOME/.codex-work codex
```

Shell aliases are useful:

```bash
alias codex-personal='CODEX_HOME=$HOME/.codex codex'
alias codex-work='CODEX_HOME=$HOME/.codex-work codex'
```

## Verification

Run these inside Codex for a personal repo:

```bash
SSH_AUTH_SOCK=/run/user/1000/codex-personal-ssh-agent.sock ssh-add -L
ssh -F ~/.config/codex/ssh-personal/config -T github.com
git ls-remote origin HEAD
```

Expected SSH result:

```text
Hi <personal-github-username>! You've successfully authenticated, but GitHub does not provide shell access.
```

Run the analogous work checks:

```bash
SSH_AUTH_SOCK=/run/user/1000/codex-work-ssh-agent.sock ssh-add -L
ssh -F ~/.config/codex/ssh-work/config -T github-work
git ls-remote origin HEAD
```

Expected SSH result:

```text
Hi <work-github-username>! You've successfully authenticated, but GitHub does not provide shell access.
```

## Troubleshooting

- `Bad owner or permissions on /etc/ssh/...`: the command is still reading system SSH config. Use
  `ssh -F ~/.config/codex/ssh-personal/config` or the work equivalent.
- `Permission denied` for `~/.ssh/known_hosts`: set `UserKnownHostsFile` to the Codex-specific
  `known_hosts` file.
- `Repository not found`: SSH authenticated as the wrong GitHub account, or the remote owner/repo is
  wrong. Check the `Hi <username>!` line from `ssh -T`.
- `Could not open a connection to your authentication agent`: set `SSH_AUTH_SOCK` for manual
  `ssh-add` checks, or confirm the configured socket exists.
- OpenSSH tries `~/.ssh/id_*`: this is normal in `ssh -G` output, but with a dedicated
  `IdentityAgent` and one key loaded, authentication should still use the intended account.
