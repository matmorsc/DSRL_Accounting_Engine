# Matching Engine Update

Extract this package directly into the existing
`DSRL_Accounting_Engine` project and allow Windows to merge folders and replace
`run.py` and `requirements.txt`.

Then run:

```powershell
pip install -r requirements.txt
pytest
python run.py
```

Expected new output:

- `data\processed\matches.csv`

The matching hierarchy is:

1. Guesty Reservation ID — confidence 100
2. Channel Reservation ID — confidence 98
3. Exact amount/date candidate in a legacy Stripe account — confidence 65–85
4. No processor match — confidence 0

Legacy Stripe candidates are never automatically approved.

After a successful test and run:

```powershell
git add .
git commit -m "Add reservation to processor matching engine"
git push
```
