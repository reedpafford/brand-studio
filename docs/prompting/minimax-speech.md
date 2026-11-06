# Prompting MiniMax speech (Speech 2.8 HD, 02 HD) and voice cloning

Official sources only, read 2026-11-06.
- **[T2A]** https://platform.minimax.io/docs/api-reference/speech-t2a-http.md
- **[Clone]** https://platform.minimax.io/docs/guides/speech-voice-clone.md · https://platform.minimax.io/docs/api-reference/voice-cloning-clone.md
- **[Voices]** https://platform.minimax.io/docs/faq/system-voice-id.md · **[Notes]** https://platform.minimax.io/docs/release-notes/models.md
- **[Pricing]** https://platform.minimax.io/docs/pricing/overview.md
- **[Rep28]** https://replicate.com/minimax/speech-2.8-hd · **[Rep02]** https://replicate.com/minimax/speech-02-hd · **[RepClone]** https://replicate.com/minimax/voice-cloning

Not read: Replicate's input schemas (empty without sign-in; we have snapshots in
`server/tests/fixtures/replicate/minimax_*.json`) and Replicate's prices. **There is no MiniMax speech model
newer than 2.8** [Notes].

## 1. Models
- Current: `speech-2.8-hd` (final quality) and `speech-2.8-turbo` (drafts). Legacy: 2.6, 02, 01 [Notes][Rep28].
- Up to 10,000 characters a call [T2A][Rep28].

## 2. Settings
- `voice_id`: a system, cloned or designed voice [T2A].
- `speed` 0.5–2 (default 1); `vol` 0–10 (default 1); `pitch` −12 to 12 (default 0) [T2A].
- `emotion`: happy, sad, angry, fearful, disgusted, surprised, calm (2.8). **`whisper` isn't supported on 2.8**;
  fluent and whisper are 2.6 only [T2A].
  **Leave it unset by default: the model picks the most natural emotion; set it only when needed** [T2A].
- `language_boost`: e.g. `English`, or `auto` [T2A].
- `text_normalization_mode`: `basic` (recommended) or `quality` (numbers, dates, money; non-streaming 2.8/2.6 only;
  falls back to basic silently) [T2A].
- Audio: sample rate up to 44,100 Hz, mp3 bitrate up to 256k, mp3/wav/flac/pcm, mono or stereo [T2A].
- `pronunciation_dict.tone`: rules like `"omg/oh my god"` or IPA `"resume/(rɪˈzjuːm)"` [T2A].
- Optional word or sentence timestamps (`subtitle_enable`, `subtitle_type: word`) [T2A].

## 3. Writing the text
- **Pauses:** `<#x#>` in seconds (0.01–99.99), placed between words, never two in a row [T2A].
- **Sounds** (2.8 only): `(laughs)`, `(chuckle)`, `(coughs)`, `(clear-throat)`, `(groans)`, `(breath)`, `(pant)`,
  `(inhale)`, `(exhale)`, `(gasps)`, `(sniffs)`, `(sighs)`, `(snorts)`, `(burps)`, `(lip-smacking)`, `(humming)`,
  `(hissing)`, `(emm)`, `(sneezes)`; the clone page also lists `(whistles)`, `(crying)`, `(applause)` [T2A][Clone].
  MiniMax writes them straight after a word, no space: `Omg(sighs), the real danger…` [T2A].
- **Pronunciation inline:** IPA in half-width brackets: `live is pronounced (lɪv) as a verb` [T2A].
- Write **numbers and dates as words** ("March fifteenth"), use proper punctuation so it breathes naturally, and
  prefer short sentences [Rep28].
- New lines for paragraph breaks [T2A].
- Dialogue: a different voice and emotion per character; speed and pitch help tell them apart [Rep28].

## 4. Voice cloning
- Sample: mp3, m4a or wav; **10 s to 5 min, 20 MB at most** (Replicate says 5 s is enough; MiniMax says 10) [Clone][RepClone].
  More audio, better accuracy [RepClone].
- Optional prompt audio under 8 s with its exact transcript, ending in punctuation: improves similarity and stability [Clone].
- `need_noise_reduction`, `need_volume_normalization` (both off by default); `text_validation` + `accuracy`
  (default 0.7) check the sample's words [Clone].
- **"If a cloned voice is not used within 7 days, the system will delete it."** [Clone]
- Which speech models a clone works with: MiniMax clones with `speech-2.8-hd` and uses it in T2A [Clone];
  Replicate's cloning page (about a year old) only promises speech-02 [RepClone]. Test 2.8 before relying on it.
- Price on MiniMax direct: $1.50 a clone, charged on first use [Pricing]. We were charged $3 through Replicate (batch-b).

## 5. Price (MiniMax direct)
- 2.8 HD: $100 per million characters ($0.10 per 1,000); turbo $60 [Pricing]. Matches our catalogue.

## 6. Where our site differs today (for the builder; nothing changed yet)
| # | Docs say | Site now | Change | Pri |
|---|---|---|---|---|
| 1 | Clones are deleted after 7 days unused | Dr. Pickle clone `R8_CJRWYITM` made 3 Nov; the site shows "may expire" from day 5 | Use it in a real test before about 10 Nov, or re-clone ($3) | must (date) |
| 2 | Leave emotion unset unless needed | Director picks an emotion or `auto` per read | Fine; the director should only set one when the line calls for it | check |
| 3 | Numbers and dates as words; short sentences | Script words never change (rule 19) | Spell digits out in the read text only (not the script), e.g. "$10" → "ten dollars"; or use `quality` normalization | should |
| 4 | `pronunciation_dict` exists | Names' pronunciation goes in a "how it's said" note | Send brand and name pronunciations (fomo, Resilia) as a dictionary on MiniMax reads | should |
| 5 | Sounds like (breath) only on 2.8 | Dr. Pickle's clone reads through 02 HD (`voices.SPEAKS`), which can't use them | Test the clone on 2.8 (MiniMax says it works) for sounds and better quality | nice |
| 6 | No whisper on 2.8 | — | The director must not ask 2.8 for a whisper | should |
