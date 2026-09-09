# Host capabilities and transcription routing (1.9)

Use this reference before processing media in a new host/runtime. The same Python CLI and JSON contracts work independently of a named Agent product; the host must actually support file access and command execution. A plain chat interface without these capabilities cannot run the local bank. Do not equate an advertised product feature with a currently callable tool. Preserve user intent and existing authorization; do not repeatedly ask for the same permissions.

## Capability check

The Agent first locates an available Python 3.10+ runtime. If none exists, explain that dependency and set it up only within the authorized workspace; do not assume `python` resolves correctly on every OS. Then run:

```text
python -B <cli> capabilities --workspace <writable-workspace> --probe-asr --host-profile <host.json> --json
```

This does not require an initialized bank. It measures Python/platform, briefly writes and removes a temporary file to check the workspace, inspects local package versions, and optionally probes imports in a bounded subprocess. Missing packages are reported without installing anything. Import success is not a loaded model, CUDA verification or a recognition accuracy test. No credentials are read or network request initiated by the adapter. Do not use the installed Skill directory as the probe workspace.

The host builds `host.json` by inspecting its **actual available tools**, not by asking the user to compose JSON. Omit unknown capabilities, or mark available=null with an explanation. All host declarations are labeled as declarations, separate from measured environment results. Example below is illustrative; replace it with facts from the current session:

```json
{
  "schema_version": 1,
  "name": "Example host",
  "capabilities": {
    "file_access": {"available": true, "evidence": "Actual file tool available in this session"},
    "command_execution": {"available": true, "evidence": "Actual command tool available in this session"},
    "image_view": {"available": null, "evidence": "Not yet established"},
    "web_search": {"available": false, "evidence": "No search tool exposed"},
    "web_read": {"available": false, "evidence": "No page-reading tool exposed"}
  },
  "transcription": null
}
```

`transcription`, when actually available, has exactly: tool, provider, execution, destination, evidence. Execution is local/remote/unknown. Remote destination is a known HTTPS service URL without credentials/query/fragment. Local and unknown use destination=null. Never infer that an Agent-native audio tool executes locally; resolve its actual service/data destination first. Store no API keys in profiles, task responses, consent, banks or Skill files.

## Route selection

After `media` intake, use:

```text
python -B <cli> media-plan --run <intake-id> --host-profile <host.json> --bank <bank> --json
```

Priority: saved transcript → supplied same-name sidecar → declared host transcription tool → optional local ASR. This is a plan: it does not attach files, upload audio or invoke a host tool. `--prefer local` or `--prefer host` selects the ASR route while still reusing existing transcripts. `--model` selects the local model name/directory.

| Route | Host action |
|---|---|
| ready | Read saved transcript with paginated media-task |
| provided | Check the single valid same-name sidecar belongs to the recording, then media-attach |
| sidecar_review | Select among ambiguous or invalid sidecars using actual source evidence; do not arbitrarily choose |
| host | Prepare handoff, invoke the declared local tool, import its real result |
| host_authorization_required | Verify that existing user authorization covers destination, file and expected charges; obtain only missing authorization before any actual upload |
| host_location_unknown | Establish service/data destination; or select a permitted local route |
| local | Execute media-transcribe; import/model/decoding errors remain possible and must be handled |
| local_setup | Install optional dependencies in the workspace and/or download model weights, or use a supplied transcript |
| blocked | Required preferred host tool is absent; report the missing capability and available alternatives |

Sidecars are matched by equal basename in the original input directory, case-insensitively. Language-suffixed subtitles require explicit selection and media-attach. Invalid or competing sidecars are exposed, not silently discarded. New media intake records the original location in its local ledger so detection works with retention=copy; retention=none removes that location after commit. Reference/retained paths are not promises of anonymization.

Provided subtitles should not also be imported as independent appearances. For mixed directories, select recordings and inspect same-name sidecars first. Once attached, the sidecar is copied into the immutable normalized transcript; changing the original subtitle later does not silently change committed questions.

## Host/local or cloud tool handoff

For a declared tool, create one source-bound task:

```text
python -B <cli> media-provider-task --run <intake-id> --source <source-id> --host-profile <host.json> --bank <bank> --json
```

For remote execution, also supply `--consent <consent.json>`. Its exact fields are provider, destination, source_sha256, cost_note and user_instruction. Provider/destination/hash must match this task. `user_instruction` records actual user authorization and `cost_note` records disclosed charges or the actual applicable account arrangement. These fields are not authorization by themselves: never fabricate a consent statement. Reuse an already authorized scope; a general request to develop the Skill does not authorize sending test recordings to a cloud service. Unknown execution location is blocked.

The returned packet identifies the file, digest and actual tool/provider. **The host invokes that tool using its documented arguments.** There is no vendor SDK, generic HTTP uploader, tool-name shell execution or platform-specific automatic connector in the Python runtime. This separation supports different tool systems and keeps their credentials/transport with the host. If the declared tool disappears, save the task and report the failure; do not substitute another external service without checking scope.

Wrap the real tool response as:

```json
{
  "schema_version": 1,
  "task_id": "run_FROM_PROVIDER_TASK",
  "source_sha256": "HASH_FROM_PROVIDER_TASK",
  "provider": {
    "tool": "actual_tool_name",
    "provider": "actual_provider",
    "execution": "local",
    "destination": null,
    "evidence": "Actual callable tool declaration copied from the task"
  },
  "format": "segments",
  "result": {
    "segments": [{"start": 1.2, "end": 3.5, "text": "数据库索引是什么？", "speaker": "SPEAKER_01"}]
  },
  "model": null,
  "engine_version": null,
  "language": "zh",
  "duration": 5
}
```

Copy provider exactly from the packet. Preserve known provider metadata; use null when absent. Supported result formats:

- segments: result.segments entries with numeric start/end in seconds (or both null), text and optional speaker/uncertain. Extra provider per-segment properties are ignored rather than copied into the bank.
- chunks: result.chunks entries with timestamp=[start,end], text and optional speaker/uncertain.
- text: a string or result.text. Nonblank lines become untimed transcript segments, never automatically questions. Do not invent timestamps.

SRT/VTT files can use the existing media-attach parser; when provider provenance is required, normalize their actual segment output before wrapping the provider result. Empty segment/chunk output needs `empty_reason` documenting the inspected no-speech result. Truncated/partial provider output must be completed before import; an unexplained missing end time is rejected. Do not silently manufacture an end time from duration.

```text
python -B <cli> media-provider-import --run <intake-id> --input <actual-response.json> --bank <bank> --json
```

Import checks task/source/provider binding, original file hash, normalized time intervals and optional duration, then atomically stores the transcript and provider receipt. Exact result retries are idempotent, including after commit. A different result cannot replace an attached transcript. Credentials and arbitrary top-level response fields are rejected. Receipts bind the adapter input, but do not independently prove a provider was called: actual tool execution and faithful result handling remain host responsibilities.

All routes converge on [media extraction](media.md): paginated reading, full segment coverage, technical-term review, classification, deduplication, sourced answers and paired exports. An ASR confidence score or provider receipt is not factual verification of the question or its answer.

## Compatibility statements

Runtime/Skill structure is designed for capable hosts on multiple platforms. Actual validation covers Windows/Python plus synthetic provider contracts; it is not a claim that every Agent, OS, cloud provider or codec has passed live integration tests. Existing local-ASR execution is tested separately. Hosts without browsing cannot complete verified-answer research; preserve pending status instead of labeling remembered answers source_backed. Hosts without image viewing can still process transcripts while reporting that screenshot extraction is unavailable.
