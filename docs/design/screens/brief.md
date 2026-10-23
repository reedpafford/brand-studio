# Brief (New video)

Purpose: a few lines about the video, so Claude can write the script. It's one short form and it creates the project.
Route: `/b/:brand/projects/new`. API: `POST /projects`.

## Fields, top to bottom
| Field | Notes |
|---|---|
| Title | required, 120 characters |
| What's it for? | textarea, optional |
| Where will it be posted? | TikTok / Instagram Reels / YouTube Shorts / Other |
| Shape | 9:16 · 1:1 · 16:9 · 4:3 · 3:4 · 21:9 (segmented) |
| Kind of video | optional, with suggestions: Story, Product ad, Explainer, Meme |
| **Product** | only for brands with products (see below) |
| Planned length (seconds) | number. Helper: "Budget: 60 credits (twice the length)." |
| Who's in it | this brand's characters (checkboxes) |
| Reference video | optional upload |

[Create project] is the primary button.

## Planned length
- There's no maximum note and no "ask Reed" note. The only helper is the budget line.
- If the server refuses the length (the per-video cap), show its message under the field as given, in `--danger`, and keep the form filled in.

## Product picker (brands with product variants)
Products come from the brand's **screens**. A screen can have a `product` and a `variant`, e.g. Iron Paws product "bag" with variants "Chicken" and "Peanut butter". The project stores the choice as `product_variants`, e.g. `{"bag": "Peanut butter"}`.
```
Bag
┌──────────┐ ┌──────────┐
│ [screen] │ │ [screen] │   one card per variant, showing that variant's screen
│ Chicken ◉│ │ Peanut   │   radio cards; selected = 2px --accent border
└──────────┘ │ butter ○ │
             └──────────┘
```
- **One group per product.** The group's label is the product name with a capital first letter ("Bag"), and it holds one radio card per variant with its screen as the thumbnail (1:1 crop on `--surface-2`). When a variant has several screens, use the first.
- A choice is required for each product the brand has. If a product has only one variant, pre-select it. Brands without products don't show the field.
- The chosen variant's screens are used as references, so the right bag appears. Enhance notes already flag a mismatch ("the line says peanut butter, the bag says chicken").
- Phone: two cards per row, each at least 44px tall.
