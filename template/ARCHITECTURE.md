# Architecture and Invariants

## Dependency Direction

```text
  data / schema / models
            ↓
  src/core (pure logic, deterministic computation, no side-effects)
            ↑
  src/storage ← src/runtime / services (orchestration, state management, persistence)
                      ↓
              src/presentation (view projection, animations)
                      ↓
                    src/ui (container layout, user interaction)
```

## Ownership

- Business state is owned and managed by Controllers/Services; state updates must be atomic.
- UI only captures intent and emits commands; it must NEVER bypass controllers to mutate state.
- Presentation only subscribes to or projects core snapshots; animation callbacks must not drive business logic.
- Storage encapsulates serialization, migrations, and integrity validation; rollback on save failures.

## Invariants

- `core` is pure deterministic logic, zero dependencies on platform APIs, I/O, networking, or views.
- State schemas support version migrations; refuse unknown/newer formats safely without corrupting backups.
- All feature changes must have automated tests protecting architectural boundaries.

## Verification & Reference

- [Architecture Check](tools/check_architecture.py) enforces dependency direction and core purity.
- Detailed domain rules are indexed in the [Documentation Index](docs/README.md).
