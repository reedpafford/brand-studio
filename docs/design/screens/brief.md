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
For brands whose kit lists products, e.g. Iron Paws: Chicken, Peanut butter.
```
Product
┌──────────┐ ┌──────────┐
│ [bag img]│ │ [bag img]│   cards 120 wide, image 1:1 on --surface-2
│ Chicken ◉│ │ Peanut   │   radio cards; selected = 2px --accent border
└──────────┘ │ butter ○ │
             └──────────┘
```
- It's required when the brand has products. Pre-select the only one if there's just one, and hide the field when there are none.
- The chosen product's bag image and name are passed to Claude and used as a reference, so the right bag appears. Enhance notes already flag a mismatch ("the line says peanut butter, the bag says chicken").
- Phone: two cards per row, each at least 44px tall.
- **Data:** this needs products on the brand kit, as a list of `{name, image_file_id}` edited under Brand kit → "Products" (name + bag image), and a `product` on the project. That's a Builder-Server item.
