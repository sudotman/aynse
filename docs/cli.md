# Command-Line Interface

`aynse` comes with a powerful command-line interface. Simply type `aynse --help` to explore all available options.

```sh
aynse --help
```

## Download Bhavcopies

```sh
aynse bhavcopy --help
```

**Download today's bhavcopy:**
(Works only after market hours)
```sh
aynse bhavcopy -d /path/to/dir
```

**Download bhavcopy for a specific date:**
```sh
aynse bhavcopy -d /path/to/dir -f 2024-01-01
```

**Download all bhavcopies between a date range:**
```sh
aynse bhavcopy -d /path/to/dir -f 2024-01-01 -t 2024-01-31
```

**Download full bhavcopies with delivery trade quantity:**
```sh
aynse bhavcopy -d /path/to/dir -f 2024-01-01 -t 2024-01-31 --full
```

**Download index bhavcopies:**
```sh
aynse bhavcopy -d /path/to/dir -f 2024-01-01 -t 2024-01-31 --idx
```

**Download derivatives bhavcopies:**
```sh
aynse bhavcopy -d /path/to/dir -f 2024-01-01 -t 2024-01-31 --fo
```

## Download Historical Stock Data

```sh
aynse stock --help
```

**Download historical stock data:**
```sh
aynse stock -s RELIANCE -f 2024-01-01 -t 2024-01-31 -o RELIANCE-Jan.csv
```

## Download Historical Index Data

```sh
aynse index --help
```

**Download historical index data:**
```sh
aynse index -s "NIFTY 50" -f 2024-01-01 -t 2024-01-31 -o NIFTY-Jan.csv
```

## Download Futures & Options Data

```sh
aynse derivatives --help
```

**Download stock futures data:**
```sh
aynse derivatives -s RELIANCE -f 2024-01-01 -t 2024-01-31 -e 2024-01-25 -i FUTSTK -o file_name.csv
```

**Download index futures data:**
```sh
aynse derivatives -s NIFTY -f 2024-01-01 -t 2024-01-31 -e 2024-01-25 -i FUTIDX -o file_name.csv
```

**Download stock call options data:**
```sh
aynse derivatives -s RELIANCE -f 2024-01-01 -t 2024-01-31 -e 2024-01-25 -i OPTSTK -p 2800 --ce -o file_name.csv
```

**Download index put options data:**
```sh
aynse derivatives -s NIFTY -f 2024-01-01 -t 2024-01-25 -e 2024-01-25 -i OPTIDX -p 21000 --pe -o file_name.csv
```
