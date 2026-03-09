from click.testing import CliRunner
from pyfakefs.fake_filesystem_unittest import TestCase
from aynse.cli import cli

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

