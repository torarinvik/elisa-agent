## Repository Hygiene and Professionalism

Treat this repository as a professional, production-quality open-source project. Maintain the standards of mature projects such as the Linux kernel, SDL, and other carefully maintained systems software.

**The repository is a deliverable, not an agent workspace, scratchpad, or diary.**

### 1. Zero Repository Clutter

- Never commit temporary files, scratch scripts, debug output, experimental implementations, logs, transcripts, or intermediate artifacts.
- Never create agent diaries, progress journals, session summaries, memory files, or similar records inside the repository.
- Do not create files such as `NOTES.md`, `PROGRESS.md`, `TODO.md`, `SESSION.md`, `DEBUG.md`, or `IMPLEMENTATION_LOG.md` merely to document your own work.
- Do not create speculative documentation, redundant READMEs, or explanations of changes that belong in commit messages.
- Keep the repository root minimal. Every top-level file and directory must have a clear, lasting purpose.
- Do not leave commented-out experiments, dead code, obsolete implementations, or temporary debugging statements.

### 2. Temporary Work Stays Outside the Repository

- Perform experiments, exploratory scripts, and temporary processing in system temporary directories whenever possible.
- If temporary files must be created inside the repository, ensure they are ignored by Git and remove them when finished.
- Do not add one-off development scripts to the repository. Only retain scripts that provide clear, reusable functionality.
- Never commit generated binaries, caches, build products, benchmark outputs, coverage reports, or temporary test results unless explicitly required as versioned project assets.
- Do not modify `.gitignore` merely to conceal clutter that should have been kept outside the repository.

### 3. Every File Must Justify Its Existence

Before creating a file, ask:

1. Is this file necessary for the actual project?
2. Does it serve a permanent, well-defined purpose?
3. Is there an existing file or mechanism that should be extended instead?
4. Would an experienced maintainer consider this file appropriate for a public release?

If a file does not clearly pass these checks, do not add it.

Prefer improving existing files over introducing unnecessary new files, directories, wrappers, abstractions, or organizational layers.

### 4. Documentation Discipline

- Documentation should describe the software, its architecture, public interfaces, development procedures, and supported behavior.
- Do not document your personal reasoning process, task history, or sequence of experiments.
- Update existing documentation when behavior changes instead of creating competing documents.
- Avoid redundant documentation and information that can be trivially derived from the source code.
- Keep documentation concise, accurate, technically useful, and maintainable.
- Create new documentation files only when they serve a clear, lasting need.

The user-authorized research diary is an exception to the general prohibition on agent diaries. Record scientific predictions, experiments, and measurements in `diary/diary-DD_MM_YY.md`, using the Europe/Oslo calendar date (for example, `diary/diary-01_11_26.md`). Append to that day's file; start a new file on a new date. Keep these entries focused on research evidence, not agent progress logs or session summaries. Preserve existing historical entries when reorganizing diary files.

Maintain mathematical theory in topic chapters under `theory/`, with `THEORY.md` as the navigation index. Keep existing section and theorem numbers stable. Extend the relevant chapter instead of restoring a monolithic theory document or using dated theory files. Add new chapters to the index and update the architecture mappings when appropriate. Keep theory focused on mathematics and model assumptions; code/proof mappings belong in `ARCHITECTURE.md`, and experiments belong in the dated research diary.

### 5. Clean, Focused Changes

- Make the smallest coherent change that correctly solves the task.
- Avoid unrelated refactoring, formatting churn, renaming, and file reorganizations.
- Do not introduce unnecessary dependencies or abstractions.
- Remove debugging code and temporary instrumentation before finishing.
- Preserve established project conventions and directory structure.
- Prefer files with fewer than 600 lines. When a file grows, consider splitting it into cohesive modules or chapters that improve clarity and maintainability; avoid arbitrary fragmentation.
- Add permanent regression tests when appropriate, but never commit disposable test harnesses or exploratory experiments.
- Do not leave multiple competing implementations when only one is needed.

### 6. Git and Commit Discipline

- Never commit files simply because they exist in the working directory.
- Review the changed-file list before committing.
- Stage files explicitly rather than blindly using `git add -A` or `git add .`.
- Verify that staged changes contain no accidental artifacts or unrelated modifications.
- Keep commits focused, meaningful, and easy to review.
- Never commit automatically unless the task or established workflow authorizes it.
- Do not discard, overwrite, or clean up pre-existing user changes or untracked files without authorization.

### 7. Mandatory Final Hygiene Check

Before completing a task:

1. Run `git status --short` and inspect every changed and untracked file.
2. Run `git diff --check` to detect whitespace errors.
3. Remove temporary artifacts created during the task.
4. Confirm that no debugging statements, experimental code, or disposable scripts remain.
5. Verify that new files are genuinely necessary and located appropriately.
6. Confirm that existing documentation was updated where necessary.
7. Ensure that only intended, task-related changes remain.

Do not delete pre-existing files or user work while performing cleanup. If suspicious files were already present, report them rather than removing them.

### 8. Default Policy

When uncertain whether something belongs in the repository, **leave it out**.

Use the conversation or final task summary to communicate progress, findings, experiments, and implementation decisions. Do not persist this information as repository files unless explicitly requested.

The final repository state should look as though it was carefully maintained by experienced human developers, not accumulated through a series of autonomous agent sessions.

**A task is not complete merely because the code works. It is complete when the code works, the changes are focused, and the repository remains clean, coherent, and publication-ready.**