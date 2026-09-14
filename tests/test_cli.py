from click.testing import CliRunner
from pyfakefs.fake_filesystem_unittest import TestCase
from aynse.cli import cli
from datetime import date
from unittest.mock import patch

class TestCli(TestCase):
    def setUp(self):
        """
        FakeFS creates a fake file systems and in process looses the CA Certs
        Which fails the test while running stocks
        To fix that CA certificates will be read and then placed back
        """
        import certifi
        self.path = certifi.where()
        with open(self.path) as fp:
            self.certs = fp.read()
        self.setUpPyfakefs()        
        ## Restoring the CA certs
        self.fs.create_file(self.path)
        with open(self.path, "w") as fp:
            fp.write(self.certs)

    def test_cli_help(self):
        """CLI root should render help and list key commands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "aynse - A command line tool" in result.output
        assert "bhavcopy" in result.output
        assert "stock" in result.output
        assert "derivatives" in result.output
        assert "mutual-fund" in result.output

    def test_holidays_cli_output(self):
        """Holidays command should print selected year and summary count."""
        runner = CliRunner()
        result = runner.invoke(cli, ["holidays", "-y", "2024"])
        assert result.exit_code == 0
        assert "Trading holidays for 2024" in result.output
        assert "Total:" in result.output
        assert "2024-01-26" in result.output

    def test_derivatives_cli_validates_options_args(self):
        """Options instrument must provide strike and option side."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "derivatives",
                "-s", "NIFTY",
                "-f", "2024-01-01",
                "-t", "2024-01-05",
                "-e", "2024-01-25",
                "-i", "OPTIDX",
            ],
        )
        assert result.exit_code != 0
        assert "Strike price" in result.output

    # def test_stock_cli(self):
    #     symbol = "RELIANCE"
    #     from_ = "2020-07-01"
    #     to = "2020-07-07"
    #     output = "/tmp/abc.csv"
    #     runner = CliRunner()
    #     cmd = "stock -s {} -f {} -t {} -o {}".format(symbol, from_, to, output)
    #     result = runner.invoke(cli, cmd.split())
    #     print(cmd)
    #     assert result.exit_code == 0
    #     with open(output) as fp:
    #         reader = csv.reader(fp)
    #         rows = list(reader)
    #         assert rows[1][0] == to
    #         assert rows[-1][0] == from_
    #         assert len(rows) == 6
        
    #     from_ = "2019-07-01"
    #     to = "2020-07-07"
    #     output = "/tmp/abc.csv"
    #     runner = CliRunner()
    #     cmd = "stock -s {} -f {} -t {} -o {}".format(symbol, from_, to, output)
    #     result = runner.invoke(cli, cmd.split())
    #     print(cmd)
    #     assert result.exit_code == 0
    #     with open(output) as fp:
    #         reader = csv.reader(fp)
    #         rows = list(reader)
    #         assert rows[1][0] == to
    #         assert rows[-1][0] == from_
    #         assert len(rows) > 200 and len(rows) < 260
     
    # def test_derivatives_cli(self):
    #     runner = CliRunner()
    #     output = "file_name.csv"
    #     cmd = "derivatives -s SBIN -f 2020-01-01 -t 2020-01-30 -e 2020-01-30 -i FUTSTK -o file_name.csv"
    #     result = runner.invoke(cli, cmd.split())
    #     assert result.exit_code == 0
    #     with open(output) as fp:
    #         reader = csv.reader(fp)
    #         rows = list(reader)
    #         assert rows[1][0] == "30-Jan-2020"
    #         assert rows[-1][0] == "01-JAN-2020"
    #         assert len(rows) == 23 
    #     cmd = "derivatives -s NIFTY -f 2020-01-01 -t 2020-01-23 -e 2020-01-23 -i OPTIDX --pe -p 12000 -o file_name.csv"
    #     result = runner.invoke(cli, cmd.split())
    #     assert result.exit_code == 0
    #     with open(output) as fp:
    #         reader = csv.reader(fp)
    #         rows = list(reader)
    #         assert rows[1][0] == "23-Jan-2020"
    #     warnings.warn("Test cannot be completed, NSE's website is providing only partial data") 

    # def test_index_cli(self):
    #     symbol = "NIFTY 50"
    #     from_ = "2020-01-01"

    #     to = "2020-03-31"
    #     output = "/tmp/abc.csv"
    #     runner = CliRunner()
    #     cmd = "index,-s,{},-f,{},-t,{},-o,{}".format(symbol, from_, to, output)
    #     result = runner.invoke(cli, cmd.split(','))
    #     print(cmd.split('.'))
    #     print(result.output)
    #     assert result.exit_code == 0
    #     with open(output) as fp:
    #         reader = csv.reader(fp)
    #         rows = list(reader)
    #         assert rows[1][1] == "31 Mar 2020"
    #         assert rows[-1][1] == "01 Jan 2020"
    #         assert len(rows) > 50


def test_mutual_fund_search_cli() -> None:
    runner = CliRunner()
    with patch(
        "aynse.cli.mutual_fund_search",
        return_value=[
            {
                "scheme_code": "122639",
                "scheme_name": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
                "latest_nav": 89.5712,
                "latest_nav_date": "2026-09-11",
            }
        ],
    ):
        result = runner.invoke(cli, ["mf", "search", "Parag Parikh", "--limit", "5"])

    assert result.exit_code == 0
    assert "122639" in result.output
    assert "89.5712" in result.output


def test_mutual_fund_history_cli() -> None:
    runner = CliRunner()
    with patch(
        "aynse.cli.mutual_fund_history_raw",
        return_value=[
            {
                "scheme_code": "122639",
                "scheme_name": "Example Direct Growth Fund",
                "date": date(2026, 9, 10),
                "nav": 20.0,
            },
            {
                "scheme_code": "122639",
                "scheme_name": "Example Direct Growth Fund",
                "date": date(2026, 9, 11),
                "nav": 20.5,
            },
        ],
    ):
        result = runner.invoke(
            cli,
            ["mutual-fund", "history", "-s", "122639", "-f", "2026-09-01", "-t", "2026-09-11"],
        )

    assert result.exit_code == 0
    assert "Example Direct Growth Fund" in result.output
    assert "2026-09-11\t20.5" in result.output


def test_mutual_fund_analyze_cli_discloses_nav_basis() -> None:
    runner = CliRunner()
    with patch(
        "aynse.cli.mutual_fund_summary",
        return_value={
            "scheme": {
                "scheme_name": "Example Direct Growth Fund",
                "plan": "Direct Plan",
                "option": "Growth",
            },
            "as_of_date": "2026-09-11",
            "metrics": {
                "observations": 252,
                "absolute_return_percent": 12.0,
                "cagr_percent": 11.5,
                "annualized_volatility_percent": 14.0,
                "max_drawdown_percent": -8.0,
            },
        },
    ):
        result = runner.invoke(
            cli,
            ["mf", "analyze", "-s", "122639", "-f", "2025-09-01", "-t", "2026-09-11"],
        )

    assert result.exit_code == 0
    assert "Absolute NAV return: 12.0" in result.output
    assert "IDCW cash distributions" in result.output
