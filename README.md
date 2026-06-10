# Index-reset pricing backtest, deploy bundle

Static web app plus weekly USDA data refresh. Models the index-reset pricing
mechanism against real USDA shipping point prints. No servers: GitHub Pages
hosts the page, a scheduled GitHub Action refreshes the data on GitHub's
machines.

## Contents

    index.html                      the app; also works opened locally
    usda_refresh.py                 pulls the MARS API, writes usda_data.js
    usda_data.js                    stub; overwritten by the first refresh
    .github/workflows/refresh.yml   schedule: Tuesday evening US Central
    setup.sh                        one-shot deploy from a code session

## Quick start in a code session

Unzip, cd into the folder, then:

    bash setup.sh produce-data-view

It prompts for your free MARS API key, creates the public repo, sets the
secret, enables Pages, and fires the first data pull. Page lives at
https://YOURNAME.github.io/produce-data-view/

## Manual path, browser only

1. New public repo on github.com; upload everything, keeping the
   .github/workflows path intact.
2. Settings, Secrets and variables, Actions: new secret MARS_API_KEY.
3. Settings, Pages: deploy from branch, main, root.
4. Actions tab, usda-refresh, Run workflow.

## Verify

The run log prints matched weeks per commodity. Zero matches on a commodity
means the report slug or spec tokens need a look:

    python3 usda_refresh.py --inspect xl_roma

shows the raw field names the API returns. Until usda_data.js holds real
rows, the app falls back to the embedded, verified XL Roma series, so the
page is never blank.

## Notes

Reference series: USDA National Shipping Point Trends, report 1662, Monday
prices released Tuesday. The pricing engine reads weekly prints only; the
daily overlay is context. A public repo means a public page: contents are
public USDA data and a generic mechanism. For gated access later, deploy the
same repo through Cloudflare Pages with access control in front.
