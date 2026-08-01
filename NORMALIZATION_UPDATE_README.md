# Normalization Update

Copy the files in this package into the root of your existing
`DSRL_Accounting_Engine` project. Allow Windows to merge folders and replace
`run.py` if prompted.

Then run:

```powershell
python run.py
```

Expected outputs:

- `data\processed\reservations.csv`
- `data\processed\processor_transactions.csv`
- `data\processed\bank_transactions.csv`
- `data\processed\quickbooks_inventory.csv`

After a successful run:

```powershell
git add .
git commit -m "Add normalized import layer"
git push
```
