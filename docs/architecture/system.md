# System Architecture

## Current stack

Tokad Mart is a retail and wholesale commerce platform with:

- Django + Django REST Framework backend
- PostgreSQL transactional database
- Redis/Celery for asynchronous work
- Next.js + TypeScript POS/admin/web client
- React Native/Expo mobile client in the companion repository

The first implementation slice is the transactional sales engine and in-shop POS.

## Architectural principles

1. Business rules belong in domain/application services rather than UI code.
2. Persistence must preserve transactional integrity and explicit state transitions.
3. APIs expose stable contracts and must validate inputs at boundaries.
4. Asynchronous work must be safe to retry and must not silently duplicate business effects.
5. UI clients consume domain behavior through APIs rather than reimplementing server-side business rules.
6. Cross-domain coupling should be explicit and documented.

## Change strategy

Before introducing a new service, abstraction, dependency, or architectural boundary:

- search for an existing implementation;
- inspect the relevant domain documentation;
- inspect applicable ADRs;
- identify affected tests and contracts;
- document a new decision when the architecture materially changes.
