# Live Data

This documentation is currently under construction.

## Quick Start

```python
from aynse.nse import NSELive

live = NSELive()
quote = live.market_status()
print(quote)
```

Notes:
- Live endpoints are cached briefly to reduce load (`live_cache`)
- Client handles retries and session priming automatically