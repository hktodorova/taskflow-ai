# Submission Checklist

Before submitting the project, verify the following items.

## Repository

- [ ] Source code is pushed to GitHub.
- [ ] `taskflow.db` is not committed (verified with `git status`).
- [ ] `README.md` is visible on the repository homepage.
- [ ] `taskflow.db`, `__pycache__` and `.pytest_cache` are not committed.
- [ ] Screenshots are inside the `screenshots/` folder.
- [ ] GitHub Actions workflow is present in `.github/workflows/tests.yml`.

## Screenshots

- [ ] `screenshots/screenshot-1-swagger-api.png`
- [ ] `screenshots/screenshot-2-user-login.png` or `screenshot-2-user-registration.png`
- [ ] `screenshots/screenshot-3-task-management.png`
- [ ] `screenshots/screenshot-4-analytics.png`
- [ ] `screenshots/screenshot-5-automated-tests.png`

## Document

- [ ] Project overview is included.
- [ ] System requirements are described.
- [ ] Architecture and modules are described.
- [ ] Development process per module is included.
- [ ] AI prompts / interactions are included.
- [ ] Challenges and tool comparison are included.
- [ ] Working system evidence contains screenshots.
- [ ] Real GitHub repository link is added.
- [ ] Google Docs sharing is set to **Anyone with the link can view**.

## Final local checks

```bash
pytest -v
uvicorn app.main:app --reload
```
