# Testing XState Delayed Transitions (after) in Vitest

## Problem

The skipped tests in our codebase were failing because XState's `after` transitions (delayed transitions) were firing immediately in the test environment when using `vi.useFakeTimers()`. This is a known issue when testing XState machines with delayed transitions.

## Solution

We found two working approaches based on the XState and Vitest documentation:

### Approach 1: Custom Clock Implementation (Recommended)

The most reliable way to test XState delayed transitions is to provide a custom clock implementation to the actor. This gives us full control over timer execution.

```typescript
// Create a simulated clock
const clock = {
  setTimeout: vi.fn((fn, ms) => {
    const id = Math.random();
    clock.timeouts.set(id, { fn, ms, time: clock.now + ms });
    return id;
  }),
  clearTimeout: vi.fn((id) => {
    clock.timeouts.delete(id);
  }),
  timeouts: new Map(),
  now: 0,
  tick: (ms: number) => {
    clock.now += ms;
    // Execute any timeouts that should fire
    for (const [id, timeout] of clock.timeouts.entries()) {
      if (timeout.time <= clock.now) {
        timeout.fn();
        clock.timeouts.delete(id);
      }
    }
  }
};

// Create actor with custom clock
const actor = createActor(machine, {
  clock: {
    setTimeout: clock.setTimeout,
    clearTimeout: clock.clearTimeout
  }
});

// Advance time in tests
clock.tick(5000); // Advance by 5 seconds
```

### Approach 2: Named Delays in Setup

When defining your machine, use named delays in the `setup()` function. This makes the delays more testable and configurable:

```typescript
const machine = setup({
  delays: {
    FLOW_TIMER: ({ context }) => {
      const stepping = context.flow?.config.stepping;
      if (stepping?.mode === 'timer') {
        return stepping.seconds * 1000;
      }
      return 0;
    }
  }
}).createMachine({
  // ... machine config
  states: {
    flowing: {
      after: {
        FLOW_TIMER: {
          // transition config
        }
      }
    }
  }
});
```

## Key Implementation Details

### 1. Compound State Structure

When using substates with timers, ensure proper initialization:

```typescript
flowing: {
  initial: 'manual', // Required for compound states
  always: [
    {
      target: 'flowing.withTimer',
      guard: ({ context }) => context.flow?.config.stepping.mode === 'timer'
    },
    {
      target: 'flowing.manual'
    }
  ],
  states: {
    manual: {},
    withTimer: {
      after: {
        FLOW_TIMER: {
          // timer transition
        }
      }
    }
  }
}
```

### 2. Timer Reset on Manual Actions

To reset timers when manual actions occur, re-enter the timer state:

```typescript
on: {
  STEP: {
    actions: assign({ /* ... */ }),
    // Re-enter to reset timer
    target: '.withTimer',
    guard: ({ context }) => context.flow?.config.stepping.mode === 'timer'
  }
}
```

### 3. Preventing Infinite Loops

Always include guards to prevent infinite timer loops:

```typescript
after: {
  FLOW_TIMER: {
    actions: assign({ /* ... */ }),
    target: 'withTimer', // Re-enter to restart timer
    guard: ({ context }) => {
      const flow = context.flow;
      return flow !== null && flow.index < flow.list.length - 1;
    }
  }
}
```

## Files Updated

1. **`src/__tests__/helpers/xstateTimerHelper.ts`** - Helper utilities for timer testing (can be refined further)
2. **`src/__tests__/flowPresetsWithClock.test.ts`** - Working example with custom clock implementation

## Tests Now Passing

- ✅ Auto-advance with timer
- ✅ Sub-second intervals
- ✅ Timer reset on manual navigation
- ✅ Flow transitions with timer
- ✅ Daily review with auto-advance

## Next Steps

To fix the remaining skipped tests:

1. Apply the custom clock approach to:
   - `autoAdvanceTimer.test.ts`
   - `mindfulMachine.test.ts`
   - The skipped test in `flowPresets.test.ts`

2. Use the same pattern:
   - Create a simulated clock in `beforeEach`
   - Pass it to `createActor`
   - Use `clock.tick()` to advance time
   - Clean up in `afterEach`

## References

- [Vitest vi.useFakeTimers documentation](https://vitest.dev/api/vi#vi-usefaketimers)
- [XState testing guide](https://stately.ai/docs/testing)
- [XState delayed transitions](https://stately.ai/docs/delayed-transitions)
- [XState clock configuration](https://stately.ai/docs/actors#system)