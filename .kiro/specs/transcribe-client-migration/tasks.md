# Implementation Plan: Transcribe Client Migration

## Overview

Migrate `transcribe.py` from the deprecated `amazon-transcribe` SDK to `aws-sdk-transcribe-streaming` v0.3.0, update the CDK layer construct description, and add tests. The Lambda handler (`lambda_function.py`) requires no changes.

## Tasks

- [x] 1. Migrate TranscribeService to new SDK
  - [x] 1.1 Replace imports and client initialization in `transcribe.py`
    - Remove all `amazon_transcribe` imports
    - Add imports from `aws_sdk_transcribe_streaming` and `smithy_aws_core`
    - Replace `TranscribeStreamingClient(region=REGION)` with new `TranscribeStreamingClient(config=Config(...))` using `EnvironmentCredentialsResolver`
    - _Requirements: 1.1, 1.2, 1.3, 7.1, 7.2_

  - [x] 1.2 Rewrite `basic_transcribe` method with new streaming API
    - Replace `start_stream_transcription` keyword args with `StartStreamTranscriptionInput` object, preserving `es-US`, `ogg-opus`, `48000` config
    - Obtain output stream via `await stream.await_output()`
    - Replace `send_audio_event(audio_chunk=chunk)` with `stream.input_stream.send(AudioStreamAudioEvent(value=AudioEvent(audio_chunk=chunk)))`
    - Replace `end_stream()` with empty audio event + `asyncio.sleep(0.4)` + `close()`
    - Keep chunk size (8192) and pacing delay unchanged
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3_

  - [x] 1.3 Replace `MyEventHandler` class with inline event handling
    - Remove `MyEventHandler` class
    - Add inline `handle_events` async function that iterates `async for event in output_stream`
    - Check `isinstance(event.value, TranscriptEvent)` and filter non-partial results
    - Collect transcript texts and return them for joining
    - Use `asyncio.gather` to run `write_chunks` and `handle_events` concurrently, join results with spaces
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 2. Update CDK layer construct
  - [x] 2.1 Update `TranscribeClient` construct description in `layers/project_layers.py`
    - Change layer description to reference `aws-sdk-transcribe-streaming`
    - _Requirements: 6.3_

- [x] 3. Checkpoint
  - Ensure all code changes compile and the CDK stack synthesizes correctly. Ask the user if questions arise.

- [ ] 4. Add tests
  - [ ]* 4.1 Write property test for endpoint URI construction
    - **Property 1: Endpoint URI construction**
    - Use `hypothesis` to generate random region strings and verify URI pattern
    - **Validates: Requirements 1.1**

  - [ ]* 4.2 Write property test for S3 URI parsing
    - **Property 2: S3 URI parsing round trip**
    - Use `hypothesis` to generate random bucket/key combinations and verify correct extraction
    - **Validates: Requirements 5.4**

  - [ ]* 4.3 Write property test for non-partial result collection
    - **Property 3: Non-partial result collection and joining**
    - Use `hypothesis` to generate mixed partial/non-partial result sequences and verify only non-partial texts appear in output
    - **Validates: Requirements 4.2, 4.3**

  - [ ]* 4.4 Write unit tests for TranscribeService migration
    - Test client initialization with mocked `TranscribeStreamingClient`
    - Test `StartStreamTranscriptionInput` parameters (`es-US`, `ogg-opus`, `48000`)
    - Test audio event wrapping and end-of-stream sequence
    - Test Lambda response format preservation
    - _Requirements: 2.1, 2.2, 5.1, 5.2, 5.3_

- [ ] 5. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The Lambda handler (`lambda_function.py`) requires no changes
- The layer zip must be rebuilt separately with `aws-sdk-transcribe-streaming~=0.3.0` and its dependencies (`smithy-aws-core[eventstream,json]~=0.3.0`, `smithy-core~=0.3.0`, `smithy-http[awscrt]~=0.3.0`)
- Property tests use `hypothesis` with minimum 100 iterations per property
