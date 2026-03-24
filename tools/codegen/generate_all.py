from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
INTERNAL_OPENAPI = ROOT / "contracts/openapi/platform-api.openapi.yaml"
ASYNCAPI = ROOT / "contracts/asyncapi/platform-events.asyncapi.yaml"
EXTERNAL_CTS = ROOT / "contracts/external/cts.validated.yaml"
PY_OUT = ROOT / "libs/py/contracts-generated/src/cvm_contracts_generated/platform_api.py"
TS_OUT = ROOT / "libs/ts/api-client-generated/src/generated"
TS_INDEX = ROOT / "libs/ts/api-client-generated/src/index.ts"
DOCS_OUT = ROOT / "docs/_generated"
TS_CANCELABLE = TS_OUT / "core/CancelablePromise.ts"


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=ROOT)


def generate_python_models() -> None:
    PY_OUT.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "uv",
            "run",
            "datamodel-codegen",
            "--input",
            str(INTERNAL_OPENAPI),
            "--input-file-type",
            "openapi",
            "--output",
            str(PY_OUT),
            "--output-model-type",
            "pydantic_v2.BaseModel",
            "--target-python-version",
            "3.12",
            "--use-standard-collections",
        ]
    )


def generate_ts_client() -> None:
    if TS_OUT.exists():
        shutil.rmtree(TS_OUT)
    run(
        [
            "pnpm",
            "run",
            "codegen:ts",
        ]
    )
    TS_CANCELABLE.write_text(
        "/* generated override for Angular compatibility */\n"
        "export class CancelError extends Error {\n"
        "  constructor(message: string) {\n"
        "    super(message);\n"
        "    this.name = 'CancelError';\n"
        "  }\n"
        "  public get isCancelled(): boolean { return true; }\n"
        "}\n"
        "export interface OnCancel {\n"
        "  readonly isResolved: boolean;\n"
        "  readonly isRejected: boolean;\n"
        "  readonly isCancelled: boolean;\n"
        "  (cancelHandler: () => void): void;\n"
        "}\n"
        "export class CancelablePromise<T> implements Promise<T> {\n"
        "  private isResolvedFlag = false;\n"
        "  private isRejectedFlag = false;\n"
        "  private isCancelledFlag = false;\n"
        "  private cancelHandlers: Array<() => void> = [];\n"
        "  private readonly promise: Promise<T>;\n"
        "  constructor(executor: (resolve: (value: T | PromiseLike<T>) => void, reject: (reason?: unknown) => void, onCancel: OnCancel) => void) {\n"
        "    this.promise = new Promise<T>((resolve, reject) => {\n"
        "      const onResolve = (value: T | PromiseLike<T>): void => {\n"
        "        if (this.isResolvedFlag || this.isRejectedFlag || this.isCancelledFlag) return;\n"
        "        this.isResolvedFlag = true;\n"
        "        resolve(value);\n"
        "      };\n"
        "      const onReject = (reason?: unknown): void => {\n"
        "        if (this.isResolvedFlag || this.isRejectedFlag || this.isCancelledFlag) return;\n"
        "        this.isRejectedFlag = true;\n"
        "        reject(reason);\n"
        "      };\n"
        "      const onCancel = ((cancelHandler: () => void): void => {\n"
        "        if (this.isResolvedFlag || this.isRejectedFlag || this.isCancelledFlag) return;\n"
        "        this.cancelHandlers.push(cancelHandler);\n"
        "      }) as OnCancel;\n"
        "      Object.defineProperty(onCancel, 'isResolved', { get: () => this.isResolvedFlag });\n"
        "      Object.defineProperty(onCancel, 'isRejected', { get: () => this.isRejectedFlag });\n"
        "      Object.defineProperty(onCancel, 'isCancelled', { get: () => this.isCancelledFlag });\n"
        "      executor(onResolve, onReject, onCancel);\n"
        "    });\n"
        "  }\n"
        "  get [Symbol.toStringTag](): string { return 'Cancellable Promise'; }\n"
        "  public then<TResult1 = T, TResult2 = never>(onFulfilled?: ((value: T) => TResult1 | PromiseLike<TResult1>) | null, onRejected?: ((reason: unknown) => TResult2 | PromiseLike<TResult2>) | null): Promise<TResult1 | TResult2> {\n"
        "    return this.promise.then(onFulfilled ?? undefined, onRejected ?? undefined);\n"
        "  }\n"
        "  public catch<TResult = never>(onRejected?: ((reason: unknown) => TResult | PromiseLike<TResult>) | null): Promise<T | TResult> {\n"
        "    return this.promise.catch(onRejected ?? undefined);\n"
        "  }\n"
        "  public finally(onFinally?: (() => void) | null): Promise<T> {\n"
        "    return this.promise.finally(onFinally ?? undefined);\n"
        "  }\n"
        "  public cancel(): void {\n"
        "    if (this.isResolvedFlag || this.isRejectedFlag || this.isCancelledFlag) return;\n"
        "    this.isCancelledFlag = true;\n"
        "    for (const cancelHandler of this.cancelHandlers) cancelHandler();\n"
        "    this.cancelHandlers = [];\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    TS_INDEX.write_text(
        "export * from './generated';\n"
        "export { OpenAPI } from './generated/core/OpenAPI';\n"
        "export { DefaultService } from './generated/services/DefaultService';\n",
        encoding="utf-8",
    )


def generate_docs() -> None:
    DOCS_OUT.mkdir(parents=True, exist_ok=True)
    internal = yaml.safe_load(INTERNAL_OPENAPI.read_text(encoding="utf-8"))
    asyncapi = yaml.safe_load(ASYNCAPI.read_text(encoding="utf-8"))
    external = yaml.safe_load(EXTERNAL_CTS.read_text(encoding="utf-8"))

    endpoints = []
    for path, methods in internal["paths"].items():
        for method, operation in methods.items():
            endpoints.append(f"- `{method.upper()} {path}`: {operation['operationId']}")

    channels = []
    for channel, content in asyncapi["channels"].items():
        message_names = ", ".join(content["messages"].keys())
        channels.append(f"- `{channel}`: {message_names}")

    external_props = external["components"]["schemas"]["CandidateSearchRequest"]["properties"].keys()

    (DOCS_OUT / "openapi-platform-api.md").write_text(
        "# OpenAPI Summary\n\n" + "\n".join(endpoints) + "\n",
        encoding="utf-8",
    )
    (DOCS_OUT / "asyncapi-platform-events.md").write_text(
        "# AsyncAPI Summary\n\n" + "\n".join(channels) + "\n",
        encoding="utf-8",
    )
    (DOCS_OUT / "external-cts.md").write_text(
        "# External CTS Summary\n\n"
        + "- Endpoint: `POST /thirdCooperate/search/candidate/cts`\n"
        + "- Request properties:\n"
        + "\n".join(f"  - `{name}`" for name in external_props)
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    generate_python_models()
    generate_ts_client()
    generate_docs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
