# aynse - NSE Data Library

`aynse` is a modern Python library for fetching data from the National Stock Exchange (NSE) of India. It provides historical data, derivatives data, bhavcopies, live market data, and trading holidays.

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Working Effectively

### Bootstrap and Dependencies
- Install Python dependencies:
  - `pip install --upgrade pip`
  - `pip install -r requirements.txt` -- takes 30-45 seconds. NEVER CANCEL.
  - `pip install -r requirements.dev.txt` -- takes 60-90 seconds. NEVER CANCEL. Set timeout to 300+ seconds.
  - `pip install -e .` -- installs package in editable mode. Takes 10-15 seconds.

### Build and Package
- Build the package:
  - `python -m build` -- takes 3-5 seconds. Creates wheel and source distribution in `dist/` directory.
  - Use `pip install build` if build module is not available.

### Run Tests
- **NEVER CANCEL TEST COMMANDS** - Tests make live API calls and can take significant time
- Run all tests: `pytest` -- takes 55-60 seconds. NEVER CANCEL. Set timeout to 120+ seconds.
- Run unittest discovery: `python -m unittest discover` -- takes 5-10 seconds. Runs fewer tests than pytest.
- Watch tests during development: `./run_tests.sh` -- uses inotifywait to auto-run tests on file changes.

### Linting and Code Quality
- Install linter: `pip install flake8`
- Check syntax errors: `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`
- Check style warnings: `flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics`
- Note: Codebase has 891 style warnings as of current state. Do not expect clean flake8 output.

### CLI Usage and Testing
- Test CLI help: `aynse --help`
- Test subcommands:
  - `aynse bhavcopy --help`
  - `aynse stock --help` 
  - `aynse derivatives --help`
  - `aynse index --help`

## Validation Scenarios

### Basic Library Validation
Always test core functionality after making changes:
```python
from datetime import date
from aynse.nse import stock_df
from aynse.holidays import holidays

# Test holidays function
h = holidays(2024)
print(f"Got {len(h)} holidays for 2024")

# Test basic imports work
print("Core imports successful")
```

### CLI Command Validation
Test CLI commands work without errors (avoid large downloads in testing):
- `aynse --help` -- should show available commands
- `aynse bhavcopy --help` -- should show bhavcopy options
- `aynse stock --help` -- should show stock data options

### Complete Workflow Testing
For any changes to data fetching logic:
1. Test import of main functions
2. Test holidays() function returns expected number of entries
3. Test CLI help commands work
4. Run at least a subset of tests to ensure no regressions

## Project Structure

### Core Directories
- `aynse/` -- Main package source code
  - `nse/` -- NSE-specific functionality (history, archives, live data)
  - `rbi/` -- RBI historical data functionality
  - `cli.py` -- Command-line interface implementation
  - `holidays.py` -- Trading holidays functionality
  - `util.py` -- Utility functions
- `tests/` -- Test suite
- `docs/` -- Documentation source files
- `.github/workflows/` -- GitHub Actions CI/CD pipelines

### Key Files
- `pyproject.toml` -- Project configuration and dependencies
- `requirements.txt` -- Runtime dependencies
- `requirements.dev.txt` -- Development dependencies  
- `README.md` -- Project documentation
- `mkdocs.yml` -- Documentation site configuration

### Build and Distribution Files
- `dist/` -- Built packages (wheel and source distribution)
- `build/` -- Temporary build artifacts
- `aynse.egg-info/` -- Package metadata

## Important Development Notes

### API Behavior
- Library makes live API calls to NSE during testing and usage
- Session setup messages "Setting up NSE session..." are normal
- Tests download real market data, causing variable execution times
- Some functions may fail if NSE website is unreachable or rate-limits requests

### Testing Considerations
- NEVER CANCEL: Tests take 55-60 seconds due to network requests. Set timeout to 120+ seconds.
- Test failures may be due to NSE API availability, not code issues
- Use pytest for comprehensive testing, unittest for faster subset testing
- Development test scripts available: `run_tests.sh` and `blog_run_test.sh`

### Build Time Expectations
- `pip install -r requirements.txt` -- 30-45 seconds
- `pip install -r requirements.dev.txt` -- 60-90 seconds  
- `python -m build` -- 3-5 seconds
- `pytest` -- 55-60 seconds
- `python -m unittest discover` -- 5-10 seconds

### CLI Commands Reference
Main commands available:
- `aynse bhavcopy -d /path/to/dir` -- Download daily bhavcopy reports
- `aynse stock -s SYMBOL -f YYYY-MM-DD -t YYYY-MM-DD -o output.csv` -- Download historical stock data
- `aynse derivatives [options]` -- Download futures and options data
- `aynse index [options]` -- Download historical index data

### Common Development Tasks
Always run these validation steps when making changes:
1. Install dependencies: `pip install -r requirements.txt && pip install -r requirements.dev.txt`
2. Install in editable mode: `pip install -e .`
3. Test basic functionality: Run the validation Python script above
4. Run tests: `pytest` (set 120+ second timeout)
5. Test CLI: `aynse --help` and verify subcommands work
6. Build package: `python -m build` to ensure it packages correctly

### Documentation
- Documentation uses MkDocs with Material theme
- Source files in `docs/` directory
- CLI documentation in `docs/cli.md`
- API documentation auto-generated from docstrings

### License and Usage
- Custom MIT license with commercial restrictions
- Free for individual use, requires permission for commercial use with >2 employees
- See LICENSE.md for full details