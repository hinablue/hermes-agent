# MEDIA delivery cache and Gateway allow roots

Session learning: image generation can succeed while Discord still shows no attachment if the final `MEDIA:` path is outside the gateway's allowed media roots. The symptom in logs is usually similar to:

```text
Skipping unsafe MEDIA directive path outside allowed roots
```

Durable pattern for this skill:

1. Treat generation success and attachment delivery as separate checks.
2. After generating the image, copy the final attachment to a Hermes media cache directory that is explicitly allowed by the running gateway.
3. Prefer reading/using the configured media roots (`HERMES_MEDIA_ALLOW_DIRS` or `gateway.media_delivery_allow_dirs`) over assuming `/home/hina/.hermes/image_cache`.
4. In profile/sandboxed runs, `Path.home()` may point at a profile home rather than the gateway owner's home, so a path that looks like a media cache may still be outside the gateway allow list.
5. Verify the cached copy exists and can be opened before final response.
6. If the user reports no image, check for the gateway warning above and resend from an allowed cache path before rerunning the whole workflow.

Do not expose the cache path in natural-language text; only use it in the `MEDIA:` directive required for platform delivery.
