# Contributing

Thank you for helping others discover Hacktoberfest projects!

We welcome contributions, but please follow the steps below to ensure consistency.

---

## 1. Fork and Clone

1. Fork this repository to your GitHub account.
2. Clone your fork locally:

```bash
git clone https://github.com/<your-username>/Hacktoberfest-25-Projects.git
cd Hacktoberfest-25-Projects
````

---

## 2. Create a Branch

Always create a new branch for your contribution. Do not work on the `main` branch directly.

* Branch naming convention:
  `project-<project-name>`

Examples:

* `project-golearn`
* `project-terminal-catacomb-crawler`
* `project-codegraphcontext`

```bash
git checkout -b project-golearn
```

---

## 3. Add Your Project

1. Open the `README.md`.
2. Add your project to the main project list.

   * Format:

     ```markdown
     | SrNo | [project-name](project-link) | tech stack | short description |
     ```
   * Keep the description short (max 120 characters).
3. Before making a PR, ensure your repository has the **`hacktoberfest` topic** added.

---

## 4. Commit Your Changes

Use clear and simple commit messages.
Format:

```
<short description>
```

Examples:

* `add golearn project`
* `add codegraphcontext project`


```bash
git add README.md
git commit -m "add golearn project"
```

---

## 5. Push Your Changes

Push your branch to your fork:

```bash
git push origin project-golearn
```

---

## 6. Create a Pull Request

1. Go to the original repository on GitHub.
2. Click **New Pull Request**.
3. Select your branch from the dropdown.

### PR Title Format

Use the same format as commit messages:
`docs: add <project-name>`

### PR Description Template

```markdown
## Description
Brief description of changes made.

## Checklist
- [ ] I confirm my project has the `hacktoberfest` topic added
- [ ] Description is within 120 characters
- [ ] The repository is active and accepts PRs
```

---

## Contribution Tips

* Only submit projects that are active and accepting PRs.
* Be respectful and follow the [Code of Conduct](CODE_OF_CONDUCT.md).
* Keep your tone friendly and open.
* Run `python3 scripts/check_projects.py` before opening a PR; it checks the numbering, the link format and that the project is not already listed. The same check runs on every pull request.

---


## Maintainers

This project is open to contributions. Feel free to add new Hacktoberfest projects or help organize the list by tech stack, difficulty, or other useful categories. Contributors who want to help maintain and improve the repository are especially welcome.

### Maintainer Guidelines

- Review pull requests promptly and provide constructive feedback.  
- Ensure new entries follow the required format and description length.  
- Keep the project list clean and organized.  
- Use clear commit messages when merging PRs. Recommended format:  

```
<type>: <short description>
```

Examples:
- `feat: reorganize project list by tech stack`
- `docs: update contributing guidelines`
- `chore: clean up formatting in README`

## Need Help?

Open an issue in this repo or ask in the Hacktoberfest Discord for tips on picking projects or making contributions.
