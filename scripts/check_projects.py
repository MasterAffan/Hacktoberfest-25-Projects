#!/usr/bin/env python3
"""Check the project table in README.md.

Usage:
    python3 scripts/check_projects.py [README.md]
    python3 scripts/check_projects.py --links [README.md]

Without options the check is offline: table shape, numbering, link format,
duplicate projects and empty cells.

With --links it also asks GitHub whether every listed repository still
exists, has moved or is archived. That needs a token in GITHUB_TOKEN or
GH_TOKEN.

The exit status is 1 when a problem is found and 0 otherwise.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import namedtuple

HEADING = "## Projects"
COLUMNS = 4
MAX_DESCRIPTION = 120
PLACEHOLDERS = {"n/a", "na", "(not specified)", "not specified", "unknown", "tbd", "-"}

LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
SEPARATOR = re.compile(r"^\|(\s*:?-+:?\s*\|)+\s*$")
GITHUB_REPO = re.compile(r"^https?://(?:www\.)?github\.com/([^/?#]+)/([^/?#]+)", re.IGNORECASE)
# First path segments on github.com that are not an account name.
NOT_AN_OWNER = {"orgs", "users", "topics", "sponsors", "marketplace", "apps"}

Row = namedtuple("Row", "line cells")
Problem = namedtuple("Problem", "line message")


def split_cells(line):
    """Split a table row into cells, keeping escaped pipes inside a cell."""
    parts = re.split(r"(?<!\\)\|", line.strip())
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1].strip() == "":
        parts = parts[:-1]
    return [part.strip() for part in parts]


def find_rows(text):
    """Return (rows, problems) for the table under the Projects heading."""
    rows = []
    problems = []
    in_section = False
    seen_separator = False
    blank_line = None
    for number, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_section:
                break
            in_section = stripped == HEADING
            continue
        if not in_section:
            continue
        if not stripped:
            if seen_separator and blank_line is None:
                blank_line = number
            continue
        if not stripped.startswith("|"):
            if seen_separator:
                break
            continue
        if not seen_separator:
            seen_separator = bool(SEPARATOR.match(stripped))
            continue
        if blank_line is not None:
            # Markdown ends a table at a blank line, so later rows show up as plain text.
            problems.append(Problem(
                blank_line, "blank line inside the table; the rows after it will not render"))
            blank_line = None
        rows.append(Row(number, split_cells(stripped)))
    return rows, problems


def repo_name(url):
    """Return 'Owner/Repo' as written in a GitHub repository URL, else None."""
    match = GITHUB_REPO.match(url)
    if not match or match.group(1).lower() in NOT_AN_OWNER:
        return None
    name = match.group(2)
    if name.lower().endswith(".git"):
        name = name[:-4]
    return match.group(1) + "/" + name


def repo_slug(url):
    """Like repo_name, in lower case; GitHub names are case-insensitive."""
    name = repo_name(url)
    return name.lower() if name else None


def link_key(url):
    """A key that is equal for two URLs pointing at the same project."""
    slug = repo_slug(url)
    if slug:
        return "github.com/" + slug
    return re.sub(r"^https?://(www\.)?", "", url.lower()).rstrip("/")


def check_table(rows):
    """Offline checks. Returns (problems, notes)."""
    problems = []
    notes = []
    if not rows:
        return [Problem(1, f'no project table found under "{HEADING}"')], notes

    expected = None
    seen = {}
    long_descriptions = 0
    for row in rows:
        cells = row.cells
        if len(cells) != COLUMNS:
            problems.append(Problem(
                row.line,
                f"row has {len(cells)} columns, expected {COLUMNS} (check for a missing or extra |)"))
            if expected is not None:
                expected += 1
            continue
        number, project, stack, description = cells

        if not number.isdigit():
            problems.append(Problem(row.line, f'Sr. No "{number}" is not a number'))
            if expected is not None:
                expected += 1
        else:
            if expected is not None and int(number) != expected:
                problems.append(Problem(row.line, f"Sr. No is {number}, expected {expected}"))
            expected = int(number) + 1

        links = LINK.findall(project)
        if not links:
            problems.append(Problem(row.line, "project cell has no [name](link)"))
        for position, (name, url) in enumerate(links):
            if not url.startswith("https://"):
                problems.append(Problem(row.line, f"link must start with https://: {url}"))
            if "?" in url:
                problems.append(Problem(row.line, f"link has a query string: {url}"))
            if url.lower().rstrip("/").endswith(".git"):
                problems.append(Problem(row.line, f"link must not end in .git: {url}"))
            key = link_key(url)
            first_line = seen.setdefault(key, row.line)
            # Only a row's main link counts; an extra link (for example a
            # backend repo) may legitimately appear under two projects.
            if position == 0 and first_line != row.line:
                problems.append(Problem(row.line, f"{name} is already listed on line {first_line}"))

        if not stack:
            problems.append(Problem(row.line, "tech stack is empty"))
        elif stack.lower() in PLACEHOLDERS:
            problems.append(Problem(row.line, f'tech stack is a placeholder ("{stack}")'))
        if not description:
            problems.append(Problem(row.line, "description is empty"))
        elif len(description) > MAX_DESCRIPTION:
            long_descriptions += 1

    if long_descriptions:
        notes.append(f"{long_descriptions} description(s) longer than {MAX_DESCRIPTION} characters")
    return problems, notes


def collect_links(rows):
    """Return (repos, others): {'Owner/Repo': line} for GitHub repos, {url: line} for the rest."""
    repos = {}
    others = {}
    seen = set()
    for row in rows:
        if len(row.cells) != COLUMNS:
            continue
        for _name, url in LINK.findall(row.cells[1]):
            name = repo_name(url)
            if name is None:
                others.setdefault(url, row.line)
            elif name.lower() not in seen:
                seen.add(name.lower())
                repos[name] = row.line
    return repos, others


def graphql(query, token):
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": "bearer " + token,
                 "User-Agent": "check-projects"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def fetch_repos(slugs, token, batch=40, run=graphql):
    """Return {name: None | {"nameWithOwner": str, "isArchived": bool}} for 'Owner/Repo' names."""
    result = {}
    slugs = list(slugs)
    for start in range(0, len(slugs), batch):
        chunk = slugs[start:start + batch]
        fields = []
        for index, slug in enumerate(chunk):
            owner, name = slug.split("/", 1)
            fields.append(
                f"r{index}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)})"
                " { nameWithOwner isArchived }")
        reply = run("query { " + " ".join(fields) + " }", token)
        data = reply.get("data")
        if data is None:
            raise RuntimeError(f"GitHub API error: {reply.get('errors') or reply}")
        # A repository that does not exist comes back as null with a
        # NOT_FOUND error; anything else means the answer can't be trusted.
        for error in reply.get("errors") or []:
            if error.get("type") != "NOT_FOUND":
                raise RuntimeError(f"GitHub API error: {error.get('message')}")
        for index, slug in enumerate(chunk):
            result[slug] = data.get(f"r{index}")
    return result


def check_repos(repos, found):
    """Turn API results into (problems, notes)."""
    problems = []
    notes = []
    for slug, line in sorted(repos.items(), key=lambda item: item[1]):
        info = found.get(slug)
        if info is None:
            problems.append(Problem(line, f"repository not found: {slug}"))
            continue
        current = info["nameWithOwner"]
        if current.lower() != slug.lower():
            problems.append(Problem(line, f"{slug} has moved to {current}"))
        if info.get("isArchived"):
            notes.append(f"line {line}: {current} is archived")
    return problems, notes


def url_status(url):
    request = urllib.request.Request(url, headers={"User-Agent": "check-projects"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError, OSError):
        return None


def check_other_links(others, status=url_status):
    problems = []
    for url, line in sorted(others.items(), key=lambda item: item[1]):
        code = status(url)
        # 401/403/429 mean the site refused an anonymous script, not that the page is gone.
        if code is None:
            problems.append(Problem(line, f"link could not be reached: {url}"))
        elif code >= 400 and code not in (401, 403, 429):
            problems.append(Problem(line, f"link returns HTTP {code}: {url}"))
    return problems


def report(path, problems, notes):
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    for problem in sorted(problems):
        if in_actions:
            print(f"::error file={path},line={problem.line}::{problem.message}")
        else:
            print(f"{path}:{problem.line}: {problem.message}")
    for note in notes:
        print("note: " + note)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check the project table in README.md.")
    parser.add_argument("readme", nargs="?", default="README.md")
    parser.add_argument("--links", action="store_true",
                        help="also check online that every link still works")
    args = parser.parse_args(argv)

    try:
        with open(args.readme, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as error:
        print(f"cannot read {args.readme}: {error}", file=sys.stderr)
        return 2

    rows, problems = find_rows(text)
    table_problems, notes = check_table(rows)
    problems += table_problems

    if args.links:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            print("--links needs a token in GITHUB_TOKEN or GH_TOKEN", file=sys.stderr)
            return 2
        repos, others = collect_links(rows)
        try:
            found = fetch_repos(repos, token)
        except (RuntimeError, urllib.error.URLError, OSError) as error:
            print(f"could not check repositories: {error}", file=sys.stderr)
            return 2
        repo_problems, repo_notes = check_repos(repos, found)
        problems += repo_problems + check_other_links(others)
        notes += repo_notes

    report(args.readme, problems, notes)
    if problems:
        print(f"{len(problems)} problem(s) in {len(rows)} projects")
        return 1
    print(f"{len(rows)} projects checked, no problems")
    return 0


if __name__ == "__main__":
    sys.exit(main())
