The SEC states that `data.sec.gov` exposes unauthenticated JSON APIs for company submissions and XBRL facts, updates them throughout the day, and publishes nightly bulk archives.[1] The SEC’s automated-access guidance sets a current maximum of 10 requests per second and requires a declared User-Agent; MarketForge’s default configuration is intentionally lower at 8 requests per second.[2] X’s current post-creation documentation uses `POST /2/tweets` with user-context authorization and returns the created post ID and text on success.[3]

## Sources

[1] https://www.sec.gov/search-filings/edgar-application-programming-interfaces — SEC EDGAR Application Programming Interfaces
[2] https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data — SEC Accessing EDGAR Data
[3] https://docs.x.com/x-api/posts/create-post — X Create Posts API
