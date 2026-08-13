# Execution Plans

Execution plans are versioned plans for work that is too large or risky to safely hold in a chat session.

## Structure

Use `active/` for work in progress and `completed/` for finished plans.

A plan should contain:

- objective and acceptance criteria;
- current architecture and affected domains;
- proposed implementation;
- database/API/UI impact;
- risks and open questions;
- verification strategy;
- progress and decision log.

Small changes may use the lightweight workflows without creating an execution plan.

## Lifecycle

```text
active/<plan>.md -> completed/<plan>.md
```

Keep plans concise and update them as implementation changes the understanding of the task.