import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_projects as cp

HEADER = (
    "# Title\n\n## Projects\n"
    "| Sr. No | Project | Tech Stack | Description |\n"
    "|--------|---------|------------|-------------|\n"
)
FOOTER = "\n## How to Contribute\n\n| not | a | project | row |\n"


def messages(*rows):
    rows, problems = cp.find_rows(HEADER + "\n".join(rows) + "\n" + FOOTER)
    table_problems, _notes = cp.check_table(rows)
    return [problem.message for problem in problems + table_problems]


def row(number, name="proj", url=None, stack="Python", description="Does things."):
    url = url or f"https://github.com/owner/{name}{number}"
    return f"| {number} | [{name}]({url}) | {stack} | {description} |"


class FindRowsTest(unittest.TestCase):
    def test_reads_only_the_projects_table(self):
        rows, problems = cp.find_rows(HEADER + row(0) + "\n" + row(1) + "\n" + FOOTER)
        self.assertEqual([r.line for r in rows], [6, 7])
        self.assertEqual(rows[0].cells[0], "0")
        self.assertEqual(problems, [])

    def test_padded_cells_are_trimmed(self):
        rows, _ = cp.find_rows(HEADER + "| 1  | [a](https://github.com/o/a)   | Go     | Text.  |\n")
        self.assertEqual(rows[0].cells, ["1", "[a](https://github.com/o/a)", "Go", "Text."])

    def test_escaped_pipe_stays_in_its_cell(self):
        rows, _ = cp.find_rows(HEADER + row(0, description=r"a \| b") + "\n")
        self.assertEqual(len(rows[0].cells), 4)

    def test_blank_line_inside_the_table(self):
        found = messages(row(0), "", row(1))
        self.assertEqual(len(found), 1)
        self.assertIn("blank line inside the table", found[0])

    def test_blank_line_after_the_table_is_fine(self):
        self.assertEqual(messages(row(0), row(1), ""), [])


class CheckTableTest(unittest.TestCase):
    def test_clean_table(self):
        self.assertEqual(messages(row(0), row(1), row(2)), [])

    def test_missing_table(self):
        problems, _ = cp.check_table(cp.find_rows("# Title\n\nNo table here.\n")[0])
        self.assertIn("no project table", problems[0].message)

    def test_numbering_gap(self):
        self.assertEqual(messages(row(0), row(1), row(3), row(4)), ["Sr. No is 3, expected 2"])

    def test_repeated_number(self):
        self.assertEqual(messages(row(5), row(5, name="other")), ["Sr. No is 5, expected 6"])

    def test_number_is_not_a_number(self):
        self.assertEqual(messages(row(0), row("x"), row(2)), ['Sr. No "x" is not a number'])

    def test_missing_closing_pipe_is_accepted(self):
        self.assertEqual(messages(row(0).rstrip(" |")), [])

    def test_extra_column(self):
        found = messages("| 0 | Name | [a](https://github.com/o/a) | Go | Text. |", row(1))
        self.assertEqual(found, ["row has 5 columns, expected 4 (check for a missing or extra |)"])

    def test_missing_column(self):
        found = messages("| 0 | [a](https://github.com/o/a) | Text. |")
        self.assertIn("row has 3 columns", found[0])

    def test_project_without_link(self):
        self.assertEqual(messages("| 0 | Name | Go | Text. |"), ["project cell has no [name](link)"])

    def test_link_format(self):
        self.assertIn("https://", messages(row(0, url="http://github.com/o/a"))[0])
        self.assertIn("query string", messages(row(0, url="https://github.com/o/a?tab=readme"))[0])
        self.assertIn(".git", messages(row(0, url="https://github.com/o/a.git"))[0])

    def test_duplicate_ignores_case_slash_and_git_suffix(self):
        found = messages(
            row(0, url="https://github.com/Owner/Repo"),
            row(1, name="again", url="https://github.com/owner/repo/"),
            row(2, name="third", url="https://github.com/owner/repo/issues"),
        )
        self.assertEqual(found, ["again is already listed on line 6", "third is already listed on line 6"])

    def test_duplicate_non_github_link(self):
        found = messages(
            row(0, url="https://gitlab.com/a/b"), row(1, name="again", url="https://gitlab.com/a/b/"))
        self.assertEqual(found, ["again is already listed on line 6"])

    def test_projects_under_one_organization_page_are_duplicates(self):
        found = messages(
            row(0, url="https://github.com/SomeOrg"), row(1, name="other", url="https://github.com/SomeOrg"))
        self.assertEqual(found, ["other is already listed on line 6"])

    def test_second_link_in_a_cell_is_not_a_duplicate(self):
        found = messages(
            "| 0 | [app](https://github.com/o/app) ([backend](https://github.com/o/api)) | Go | Text. |",
            "| 1 | [web](https://github.com/o/web) ([backend](https://github.com/o/api)) | Go | Text. |",
        )
        self.assertEqual(found, [])

    def test_placeholder_and_empty_cells(self):
        self.assertEqual(messages(row(0, stack="N/A")), ['tech stack is a placeholder ("N/A")'])
        self.assertEqual(messages(row(0, stack="(Not specified)")),
                         ['tech stack is a placeholder ("(Not specified)")'])
        self.assertEqual(messages("| 0 | [a](https://github.com/o/a) |  | Text. |"), ["tech stack is empty"])
        self.assertEqual(messages("| 0 | [a](https://github.com/o/a) | Go |  |"), ["description is empty"])

    def test_long_descriptions_are_a_note_not_a_problem(self):
        rows, _ = cp.find_rows(HEADER + row(0, description="x" * 121) + "\n" + row(1, description="x" * 120))
        problems, notes = cp.check_table(rows)
        self.assertEqual(problems, [])
        self.assertEqual(notes, ["1 description(s) longer than 120 characters"])


class LinkHelpersTest(unittest.TestCase):
    def test_repo_slug(self):
        self.assertEqual(cp.repo_slug("https://github.com/Owner/Repo"), "owner/repo")
        self.assertEqual(cp.repo_slug("https://github.com/owner/repo.git"), "owner/repo")
        self.assertEqual(cp.repo_slug("https://github.com/owner/repo/tree/main"), "owner/repo")
        self.assertEqual(cp.repo_slug("https://github.com/owner/my.site"), "owner/my.site")
        self.assertIsNone(cp.repo_slug("https://github.com/owner"))
        self.assertIsNone(cp.repo_slug("https://github.com/owner/"))
        self.assertIsNone(cp.repo_slug("https://github.com/orgs/owner/projects/1"))
        self.assertIsNone(cp.repo_slug("https://gitlab.com/owner/repo"))

    def test_collect_links(self):
        rows, _ = cp.find_rows(
            HEADER
            + row(0, url="https://github.com/O/A") + "\n"
            + row(1, url="https://gitlab.com/o/b") + "\n"
            + row(2, url="https://github.com/SomeOrg") + "\n"
            + row(3, url="https://github.com/o/a/issues") + "\n"
        )
        repos, others = cp.collect_links(rows)
        self.assertEqual(repos, {"O/A": 6})
        self.assertEqual(others, {"https://gitlab.com/o/b": 7, "https://github.com/SomeOrg": 8})


class OnlineChecksTest(unittest.TestCase):
    def test_fetch_repos_batches_and_maps_results(self):
        queries = []

        def run(query, token):
            queries.append(query)
            self.assertEqual(token, "t")
            count = query.count("repository(")
            data = {f"r{i}": {"nameWithOwner": f"X/Y{i}", "isArchived": False} for i in range(count)}
            data["r0"] = None
            return {"data": data, "errors": [{"type": "NOT_FOUND", "message": "gone"}]}

        found = cp.fetch_repos(["o/a", "o/b", "o/c"], "t", batch=2, run=run)
        self.assertEqual(len(queries), 2)
        self.assertIn('repository(owner: "o", name: "a")', queries[0])
        self.assertIsNone(found["o/a"])
        self.assertEqual(found["o/b"]["nameWithOwner"], "X/Y1")
        self.assertIsNone(found["o/c"])

    def test_fetch_repos_rejects_other_api_errors(self):
        def rate_limited(query, token):
            return {"data": {"r0": None}, "errors": [{"type": "RATE_LIMITED", "message": "slow down"}]}

        def no_data(query, token):
            return {"message": "Bad credentials"}

        with self.assertRaises(RuntimeError):
            cp.fetch_repos(["o/a"], "t", run=rate_limited)
        with self.assertRaises(RuntimeError):
            cp.fetch_repos(["o/a"], "t", run=no_data)

    def test_check_repos(self):
        repos = {"o/gone": 6, "O/Moved": 7, "o/old": 8, "o/fine": 9, "o/case": 10}
        found = {
            "o/gone": None,
            "O/Moved": {"nameWithOwner": "New/Home", "isArchived": False},
            "o/old": {"nameWithOwner": "o/old", "isArchived": True},
            "o/fine": {"nameWithOwner": "o/fine", "isArchived": False},
            "o/case": {"nameWithOwner": "O/Case", "isArchived": False},
        }
        problems, notes = cp.check_repos(repos, found)
        self.assertEqual(
            [(p.line, p.message) for p in problems],
            [(6, "repository not found: o/gone"), (7, "O/Moved has moved to New/Home")],
        )
        self.assertEqual(notes, ["line 8: o/old is archived"])

    def test_check_other_links(self):
        codes = {"https://a": 200, "https://b": 404, "https://c": None, "https://d": 403, "https://e": 500}
        problems = cp.check_other_links({url: n for n, url in enumerate(codes, 1)}, status=codes.get)
        self.assertEqual(
            [p.message for p in problems],
            ["link returns HTTP 404: https://b", "link could not be reached: https://c",
             "link returns HTTP 500: https://e"],
        )


class MainTest(unittest.TestCase):
    def run_main(self, text, *options, env=None):
        """Run main() on a temporary README with a known environment."""
        clean = {
            name: value
            for name, value in os.environ.items()
            if name not in ("GITHUB_ACTIONS", "GITHUB_TOKEN", "GH_TOKEN")
        }
        clean.update(env or {})
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "README.md")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            out, err = io.StringIO(), io.StringIO()
            environment = mock.patch.dict(os.environ, clean, clear=True)
            with environment, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cp.main([path, *options])
        return code, out.getvalue(), err.getvalue()

    def test_exit_codes(self):
        code, out, _ = self.run_main(HEADER + row(0) + "\n" + row(1) + "\n")
        self.assertEqual(code, 0)
        self.assertIn("2 projects checked, no problems", out)

        code, out, _ = self.run_main(HEADER + row(0) + "\n" + row(2) + "\n")
        self.assertEqual(code, 1)
        self.assertIn("README.md:7: Sr. No is 2, expected 1", out)

    def test_missing_file(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cp.main(["/nonexistent/README.md"]), 2)

    def test_links_without_token(self):
        code, _, err = self.run_main(HEADER + row(0) + "\n", "--links")
        self.assertEqual(code, 2)
        self.assertIn("needs a token", err)

    def test_actions_annotations(self):
        _, out, _ = self.run_main(HEADER + row(0) + "\n" + row(2) + "\n", env={"GITHUB_ACTIONS": "true"})
        self.assertRegex(out, r"::error file=.*README\.md,line=7::Sr\. No is 2, expected 1")


if __name__ == "__main__":
    unittest.main()
