# llm-proof

A CLI tool that turns a plain PDF into a protected PDF: password-protected so that naive LLM ingestion fails to open it, and carrying canaries so that unauthorised extraction can be identified.

## Language

**Canary**:
Invisibly embedded text planted in a protected document, which identifies who or what extracted the content when it surfaces.
_Avoid_: Watermark, trap, breadcrumb, honeytrap

**Canary spec**:
The user-written text of canaries, one per `---`-separated block, where a separator may carry a placement directive for its canary.
_Avoid_: Trap list

**Canary spec file**:
A file carrying a canary spec, read by `--canaries-file`.
_Avoid_: Canary file, trap list

**Placement mode**:
How a canary is anchored on its page: text-anchored (after a word of the page's text) or geometric (at the top, centre, or bottom of the page).
_Avoid_: Insertion mode, position

**Placement directive**:
An optional key on a canary spec separator (e.g. `page: 7, centre`) controlling where a canary is embedded in the document: which page, and its placement mode on that page.
_Avoid_: Locator, target

**Canonical content**:
A document's body text in reading order, whitespace-normalised, excluding annotation text. The basis of the seed, computed from the plain document.
_Avoid_: Text dump, extraction

**Seed**:
The per-document value derived from the canonical content, carried in the protected document and readable without the password. Mixed with the salt to yield the derived password; because the seed travels with the document, the salt is the only secret to keep.
_Avoid_: Document identity, fingerprint, key, hint

**File ID**:
The PDF trailer's `/ID` entry: an array of two byte strings, carried unencrypted in the file. The clear-text carrier of the marked seed in a protected document; in other PDFs it holds values that are not seeds.
_Avoid_: Document ID, fingerprint, file key

**Marker**:
The user-chosen label that prefixes the seed where it is carried in the protected document, so the seed can be recognised and distinguished from other file IDs. Held outside the document, like the salt; a document protected under one marker re-derives only under the same marker.
_Avoid_: Signature, magic string, watermark

**Salt**:
The user-held secret, held outside the document, mixed with the seed to yield the derived password.
_Avoid_: Pepper, secret key, passphrase

**Derived password**:
The password derived from the seed with a user-held salt; used as the PDF's user and owner password.
_Avoid_: Key, passphrase, secret

**Protected document**:
The output of `protect`: a PDF encrypted with its derived password, canaries embedded, carrying its seed.
_Avoid_: Encrypted PDF, locked PDF

**Plain document**:
A PDF without a password; the input to `protect`.
_Avoid_: Source PDF, input

**Release**:
A versioned publication of release artifacts on GitHub, identified by its semver tag.
_Avoid_: Version, build, distribution

**Release artifact**:
A platform-specific executable published as a release asset, named for its platform and architecture.
_Avoid_: Binary, package, build output

**Self-update**:
The installed executable replacing itself with a newer release artifact.
_Avoid_: Auto-update, upgrade

**Update check**:
The query for the latest release performed when a command runs.
_Avoid_: Version ping, health check

**Update notice**:
The message shown when a newer release is available than the running version.
_Avoid_: Banner, alert, prompt
