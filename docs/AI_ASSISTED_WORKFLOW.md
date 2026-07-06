# AI-Assisted Development

I used ChatGPT and GitHub Copilot throughout this project. ChatGPT was useful for planning the architecture early on — I described what I wanted to build and it helped break it into modules. Copilot handled most of the repetitive endpoint and CRUD boilerplate.

The general loop was: describe what I needed, review what came back, run the tests, then fix what broke. The auth flow and the cycle detection for task dependencies needed quite a bit of manual work to get right.

By module, the AI contribution was different. Architecture planning was most useful for the layered split between API, service and repository code. CRUD scaffolding was the fastest part to generate, while authentication, dependency validation and test-driven fixes needed the most manual correction and review.

## Some prompts I found useful

- "Design a modular FastAPI architecture for a task management system."
- "Add JWT Bearer token authentication with role-based access."
- "Write pytest tests for user registration, login and task CRUD."
- "Here is the traceback — what's the smallest fix?"

## How it actually went

Not everything the AI generated worked on the first try. The test suite was the main feedback loop — a failing test usually became the next prompt. I reviewed all generated code before committing and made manual corrections where the logic wasn't quite right.

The final structure reflects both what the AI suggested and the adjustments I made after running it.

This was especially visible in the authentication and validation paths, where AI accelerated the first draft, but the final behavior depended on manual review, targeted fixes and rerunning the tests until the API behavior matched the intended design.
