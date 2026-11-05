# Your own photos

Use this folder when an AI image is rejected and you want to post your own photo instead.

1. Name the photo after the post it replaces:
   - `tue.jpg` replaces the next Tuesday post that hasn't gone out yet (same for `sun`, `wed`, `thu`, `sat`)
   - `2026-11-08_tue.jpg` replaces the Tuesday post of a specific batch
2. Upload it here: **Add file > Upload files**, then **Commit changes**. JPG, PNG or WEBP.
3. The **Use Manual Image** workflow starts by itself. It crops the photo to 1080x1350
   (keep the subject near the center), writes the caption for that post's city and
   language, removes the rejected AI image, and marks the post **approved**.
   It posts at its scheduled time.

The photo is removed from this folder once it is attached. Check the workflow run's
summary page to read the caption it wrote.
