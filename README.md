# MycoPatch

한국어 | [English](README.en.md)

MycoPatch는 코드베이스를 위한 오프라인 면역 시스템입니다.

## 핵심 가치

MycoPatch의 핵심 가치는 **AI가 코드를 고치기 전에, 먼저 재현 가능한 증거를 만든다**는 것입니다.

일반 코딩 에이전트는 사용자가 버그를 설명하면 바로 패치를 만들려고 합니다. MycoPatch는 반대로 움직입니다. 저장소를 먼저 스캔하고, 취약해 보이는 부분을 찾고, 작은 probe/test를 만들고, 실행 결과와 비용을 기록한 뒤에야 수정 방향을 추천합니다.

이 CLI를 쓰는 이유는 명확합니다.

- 아직 드러나지 않은 위험한 코드를 먼저 찾기 위해
- 그럴듯하지만 근거 없는 AI 패치를 줄이기 위해
- 버그 의심 지점을 작은 테스트와 리포트로 남기기 위해
- 모델이 바뀌어도 남는 `.myco/` immune memory를 쌓기 위해
- 외부 API, 네트워크, 위험한 command 없이 local-first로 검사하기 위해
- Python/JavaScript/TypeScript의 반복 버그 패턴을 안전하게 탐지하고, Go/Rust/Java/.NET/Ruby/PHP 같은 대중적인 생태계의 검증 경로를 안전하게 확인하기 위해

한 줄로 말하면, MycoPatch CLI는 **자동 패치 생성기**가 아니라 **코드베이스의 약한 곳을 조용히 찾아내고, 증거를 남기는 안전한 버그 헌팅 도구**입니다.

대부분의 코딩 에이전트는 사용자가 버그를 설명할 때까지 기다립니다. MycoPatch는 저장소를 스캔하고, 취약할 가능성이 높은 영역을 예측하고, 작은 probe를 만들고, 안전하게 실행하고, 근거를 기록하며, 재사용 가능한 immune memory를 `.myco/` 아래에 보관합니다.

버전 0.7의 범위는 의도적으로 안전합니다. 기존 다중 생태계 탐지와 검증에 더해, 명시적으로 요청한 경우에만 known-pattern의 guarded unified diff와 rollback 문서를 초안으로 만듭니다. MycoPatch가 애플리케이션 소스에 patch를 적용하지는 않습니다.

## 무엇이 다른가

- Pull request는 항체입니다. 패치는 재현 가능한 근거에 답해야 합니다.
- 테스트는 보이는 증상입니다. 수정 전에 probe가 위험을 드러내야 합니다.
- Spore는 재사용 가능한 버그 패턴 캡슐입니다. 위험 지식은 특정 모델 하나에 묶이지 않습니다.
- Immune memory는 모델이 바뀌어도 남습니다. 발견 사항과 결과는 append-only JSONL로 기록됩니다.
- 기본값은 local-first입니다. API 호출, 백그라운드 서비스, 네트워크 의존성이 없습니다.

## 설치

로컬 개발 환경에서는 다음처럼 설치합니다.

```bash
pip install -e ".[dev]"
```

CLI를 확인합니다.

```bash
myco --help
pytest
```

## 빠른 시작

Python 또는 JavaScript/TypeScript 저장소 루트에서 실행합니다.

```bash
myco init
myco init  # 다시 실행해도 안전합니다. 기존 .myco 레이아웃을 확인합니다.
myco scan
myco ecosystems
myco risks
myco explain
myco hunt --budget 30000 --mode safe
myco verify --no-run
myco doctor
myco report
myco memory
myco patch
myco patch --draft-diffs
myco --version
```

예상 동작:

- `myco init`은 `.myco/`를 만들고, 내장 spore를 설치하며, 여러 번 실행해도 안전합니다.
- `myco scan`은 감지된 Python 파일, JS/TS 파일, ecosystem, 테스트, 상위 위험, 오프라인 비용 추정을 포함한 `.myco/reports/repo_weather.md`를 작성합니다.
- `myco ecosystems`는 Python, JS/TS, Go, Rust, Java/Kotlin, .NET, Ruby, PHP manifest와 framework hint, 검증 profile 후보를 보여줍니다.
- `myco risks`는 score, confidence, nearby-test 여부, 첫 번째 evidence line을 포함한 상위 finding을 출력합니다.
- `myco explain`은 발견된 위험이 왜 문제인지 사람에게 읽기 쉬운 설명과 review step으로 보여줍니다.
- `myco hunt --budget 30000 --mode safe`는 결정론적 오프라인 휴리스틱을 사용합니다. budget은 예상 token의 hard limit이며, 부족하면 probe를 만들지 않고 inconclusive event를 기록합니다.
- `myco hunt --budget 30000 --mode aggressive`는 정적 근거가 명확할 때 실패하는 probe를 만들 수 있습니다. Aggressive probe는 명확히 라벨링되고, 생성된 테스트 옆에 설명용 Markdown 파일을 작성하며, 애플리케이션 소스 파일은 수정하지 않습니다.
- `myco hunt --dry-run`, `--language`, `--file`, `--limit`, `--all`로 probe 생성을 미리 확인하거나 특정 risk만 대상으로 지정할 수 있습니다.
- `myco scan --json`과 `myco risks --json`은 script와 CI에서 쓰기 좋은 machine-readable output을 출력합니다.
- `myco verify --no-run`은 실행 가능한 프로젝트 검증 profile을 보여주는 dry-run입니다.
- `myco verify --run --allow-project-tests`는 MycoPatch가 인정한 프로젝트 테스트 profile을 해당 manifest 디렉터리에서 실행합니다. 테스트 실패나 정책 차단은 종료 코드 1을 반환합니다.
- `myco doctor`는 도구 사용 가능 여부, config, provider network 상태와 JSONL 손상 위치를 확인합니다.
- `myco report`는 memory event, probe 결과, 0달러 오프라인 cost ledger를 요약합니다.
- `myco memory`는 `.myco/memory/*.jsonl`에 쌓인 append-only 이벤트를 CLI에서 조회합니다.
- `myco patch`는 임의의 소스 파일을 자동 수정하지 않습니다. 재현 가능한 probe failure가 기록된 경우에만 recommendation을 작성합니다.
- `myco patch --draft-diffs`는 eligible aggressive failure에 대해 `.myco/reports/patches/` 아래에 unified diff와 rollback 문서를 만듭니다. v0.7의 내장 변환은 Python `datetime.utcnow()` 한 가지로 제한되며 source에는 적용하지 않습니다.

## `.myco/` 디렉터리

```text
.myco/
  memory/
    repo_constitution.md
    failure_patterns.jsonl
    accepted_patches.jsonl
    rejected_patches.jsonl
    negative_results.jsonl
  spores/
    python-timezone-boundary.yaml
    js-ts-timezone-boundary.yaml
    python-mutable-default-argument.yaml
    python-broad-exception-swallow.yaml
  probes/
    generated_tests/
  reports/
    repo_weather.md
    cost_ledger.jsonl
    immune_history.md
    guarded_patch_drafts.md
    patches/
  config.toml
```

이 디렉터리는 감사 가능하고 append-oriented입니다. 이 저장소의 `.gitignore`에서는 기본적으로 제외되어 있으며, downstream 프로젝트는 immune memory를 커밋할지 직접 결정할 수 있습니다.

## Spores

Spore는 위험 패턴, trigger, probe strategy, budget, safety constraint를 설명하는 YAML 캡슐입니다.

내장 spore:

- `python-timezone-boundary`: `datetime.now`, `datetime.utcnow`, `date.today`, naive datetime construction, timezone-naive comparison, 그리고 billing, invoice, subscription, expiry, renewal, deadline, payment, report 같은 비즈니스 이름을 찾습니다.
- `js-ts-timezone-boundary`: `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.cjs` 파일에서 `new Date()`, `Date.now()`, `Date.parse(...)`, `new Date("YYYY-MM-DD")`, local date getter/setter, 그리고 같은 timezone-sensitive 비즈니스 이름을 찾습니다.
- `python-mutable-default-argument`: `def f(items=[])`처럼 호출 사이에 상태가 공유될 수 있는 mutable default argument를 찾습니다.
- `python-broad-exception-swallow`: `except Exception: pass`처럼 실패 증거를 숨길 수 있는 broad exception swallowing 패턴을 찾습니다.

JS/TS probe는 기본적으로 dependency-free입니다. Node 내장 `node:test` runner를 사용하고, 대상 source file을 text로 읽으며, 애플리케이션 코드를 import하거나 package-manager command를 실행하지 않습니다.

## 안전 모델

MycoPatch는 위험한 command를 기본적으로 차단하고, 좁은 local command set만 허용합니다.

- `python --version` 또는 `python3 --version`
- generated probe용 `pytest .myco/probes/generated_tests/*.py`
- `node --test .myco/probes/generated_tests/*.mjs`
- `git status`
- `git diff`

v0.6.1의 `myco verify`는 프로젝트 테스트 명령을 기본적으로 실행하지 않습니다. 허용 시에도 proxy 차단과 생태계별 offline 환경을 적용합니다. 이는 package download를 억제하는 방어 계층이며, 명시적으로 허용한 프로젝트 테스트 코드의 직접 socket 접근까지 격리하는 OS sandbox는 아닙니다.

`npm`, `npx`, `yarn`, `pnpm`, `pip install`, `go get`, `cargo install`, `bundle install`, `composer install`, `dotnet restore` 같은 dependency install 또는 network-prone command는 차단됩니다. 생성된 probe는 기본적으로 애플리케이션 코드를 import하지 않습니다. 프로젝트별 동작을 환각하지 않고 pipeline을 검증하기 위한 executable risk marker로 동작합니다.

Aggressive probe는 opt-in입니다. 위험한 정적 패턴이 남아 있는 동안 의도적으로 실패할 수 있지만, `.myco/probes/generated_tests/` 아래에만 작성되고 human review를 위한 Markdown 설명을 포함합니다.

## 선택적 모델 Provider

MycoPatch는 offline-first입니다. `.myco/config.toml`의 기본값은 다음과 같습니다.

```toml
default_provider = "offline"
model_name = "offline-heuristic"
allow_network_for_model_provider = false
allow_project_test_commands = false
```

Provider 인터페이스는 advisory task로 제한됩니다.

- failure log 요약
- probe idea 제안
- patch recommendation text 초안 작성

Provider는 직접적인 source-code diff 생성이나 patch 적용에 사용되지 않습니다. guarded diff는 결정론적인 로컬 변환만 사용합니다. 외부 provider는 `allow_network_for_model_provider = true`와 0보다 큰 `max_cost_usd`가 모두 설정된 경우에만 호출됩니다.

## 현재 제한 사항

- 지원 spore는 아직 작고 결정론적인 패턴으로 제한됩니다.
- 다중 생태계 지원은 탐지와 안전 검증 profile 중심입니다. 모든 언어에 깊은 버그 패턴 분석이 들어간 것은 아닙니다.
- JS/TS 지원은 정적 분석 기반이며 dependency-free입니다. 전체 TypeScript semantics를 파싱하지 않고, 파일을 transpile하지 않으며, 아직 Jest/Vitest와 통합하지 않습니다.
- Probe generation은 휴리스틱입니다. Safe mode는 보수적이고, aggressive mode도 정적 근거만 사용합니다.
- Guarded patch generation은 opt-in artifact drafting입니다. 자동 적용은 없고, 현재 Python `datetime.utcnow()`만 지원합니다.
- Model provider는 advisory 용도입니다. 모델 출력으로 source patching을 수행하지 않습니다.
- 자율적인 source-code modification은 없습니다.

## Roadmap

- v0.1: 오프라인 Python/pytest MVP.
- v0.2: safe/aggressive probe mode, AST 기반 datetime evidence, confidence scoring, risk table.
- v0.3: offline-first cost tracking을 포함한 선택적 advisory model-provider 인터페이스.
- v0.4: Node 내장 test runner를 사용하는 dependency-free JS/TS timezone probe.
- v0.5: Python mutable default, broad exception swallowing, `myco explain`, `myco memory`.
- v0.6: Python, JS/TS, Go, Rust, Java/Kotlin, .NET, Ruby, PHP ecosystem 탐지와 명시 허용 기반 project verification profile.
- v0.6.1: command-policy 우회 차단, symlink 경계, 모노레포 working directory, JSONL 복구, 실제 budget/종료 코드, 릴리스 CI 강화.
- v0.7: known-pattern failure 기반의 opt-in guarded diff/rollback artifact. source 자동 적용 없음.
- v0.8: local model routing.
- v1.0: spore marketplace와 shared immune memory workflow.
