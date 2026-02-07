# Supabase: Can't See Products in Dashboard

If the scraper logs show "Inserted product" and **HTTP 201 Created** but you see **no rows** in the Table Editor, the data is almost certainly in the database and **Row Level Security (RLS)** is hiding it when you view the table.

## 1. Confirm the data exists (SQL Editor)

In Supabase: **SQL Editor** → New query, run:

```sql
SELECT COUNT(*) FROM public.products;
SELECT id, title, source, created_at FROM public.products ORDER BY created_at DESC LIMIT 10;
```

- If you see a count (e.g. 189) and rows: data is there. The Table Editor is just not allowed to read it because of RLS.
- If count is 0: then we're inserting into another schema/project or something else is wrong (unlikely given 201 responses).

## 2. Check RLS on `products`

In **SQL Editor**:

```sql
SELECT relname, relrowsecurity
FROM pg_class
WHERE relname = 'products';
```

If `relrowsecurity` is `true`, RLS is enabled. With RLS on, every role needs an explicit policy to SELECT/INSERT/UPDATE/DELETE.

## 3. Allow reading products (so Dashboard and app can see them)

Run in **SQL Editor** (this allows all clients, including anon, to read rows):

```sql
-- Allow anyone to read products (anon + service role)
CREATE POLICY "Allow read products"
ON public.products
FOR SELECT
USING (true);
```

If you prefer to allow only authenticated users to read:

```sql
CREATE POLICY "Allow authenticated read products"
ON public.products
FOR SELECT
TO authenticated
USING (true);
```

After adding the policy, refresh the **Table Editor** for `products`; you should see the rows.

## 4. Optional: allow only your scraper to insert

Your scraper uses the **service role** key, which bypasses RLS. To keep RLS but allow only the service role to insert (and allow reads as above):

```sql
CREATE POLICY "Allow service role insert products"
ON public.products
FOR INSERT
TO service_role
WITH CHECK (true);
```

(Usually service_role already bypasses RLS, so this is only needed if you lock down other roles and want an explicit policy.)

## Summary

| Symptom | Cause | Fix |
|--------|--------|-----|
| Logs say "Inserted", 201, but Table Editor is empty | RLS is ON, no SELECT policy | Add `FOR SELECT USING (true)` policy on `public.products` |
| Count in SQL is 0 | Wrong table/schema/project or RLS on a role that runs the count | Run the COUNT in SQL Editor (uses your project); check schema `public` |
