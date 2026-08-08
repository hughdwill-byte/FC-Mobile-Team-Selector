# Publishing the live website (one-time, ~1 minute)

The website is a plain static site in the **`docs/`** folder. GitHub can host it **free** at a
clean `github.io` link — you don't run anything on your computer. Do this once:

1. On GitHub, open your repo → **Settings** (top bar) → **Pages** (left sidebar).
2. Under **Build and deployment → Source**, choose **Deploy from a branch**.
3. Set **Branch** to the branch that has this code, and the folder to **`/docs`**:
   - To publish immediately from the current branch, pick
     **`claude/project-docs-setup-guide-ofr8zw`** and **`/docs`**.
   - Or, once this is merged, pick your default branch (e.g. `main`) and **`/docs`**.
4. Click **Save**.

Wait ~1 minute. The Pages panel will then show your live URL, which will be:

```
https://hughdwill-byte.github.io/FC-Mobile-Team-Selector/
```

That's the link to share. Every time you push changes to that branch, the site updates
automatically.

---

### Notes
- The site is 100% client-side: player data is stored in each visitor's own browser
  (localStorage). Nothing is uploaded, and different visitors never see each other's squads.
- Because it's static, there are **no running costs and nothing to keep awake** — unlike a
  server host, it never sleeps and loads instantly.
- Want a custom domain later? Pages supports it under the same **Settings → Pages** screen.
