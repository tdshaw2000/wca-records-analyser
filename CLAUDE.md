# CLAUDE.md — WCA Records Analyser

> This file defines the working standards for this project.
> Claude must follow all rules below at all times, without exception.

---

## project summary

- **Name:** WCA Records Analyser
- **Purpose:** This project will use data available at https://www.worldcubeassociation.org, which is the official website for speedcubing and contains all competition data for competitive speedcubers. The idea is that you can search for a member, select a puzzle that they have competed in, and produce a graph of their personal records.

## tech stack

- **Language:** Python
- **CI/CD:** gitlab

## test-driven development

- **Tests first.** Write a failing test before writing any production code. No exceptions.
- The red-green-refactor cycle is mandatory: red → green → refactor.
- **Never mix test changes and business logic changes in the same commit.** Each commit must touch either tests or production code, not both.
- **Never modify an existing test to make failing code pass.** If a test is wrong, raise it explicitly and wait for direction. Fix the implementation, not the contract.

## commit discipline

- Commit frequently. Do not accumulate large diffs. Every logical unit of work is a candidate for a commit.
- Each commit must represent exactly one logical change. If you find yourself writing "and" in a commit message, split the commit.
- Commit messages follow **Conventional Commits (feat/fix/chore/test)** format.

## code style

- **Constants over literals.** All magic numbers and string literals must be extracted into named constants. Inline literals (other than 0, 1, empty string, true/false) are not permitted in business logic.
- **Meaningful, unabbreviated names.** Identifiers must be self-documenting. Avoid abbreviations unless they are universally understood domain terms.
- **Single responsibility.** Methods do one thing. Classes own one concept. If you need "and" to describe what a method does, split it.
- **No dead code.** Remove unused methods, variables, imports, and classes. Do not comment out code — delete it. Version control is the history.

## working style

- Explain your reasoning before making changes, especially when multiple approaches exist.
- If a requirement is ambiguous, ask a clarifying question before proceeding.
- After each commit-worthy change, pause and confirm before moving to the next step.
- Do not refactor and add functionality in the same step.
