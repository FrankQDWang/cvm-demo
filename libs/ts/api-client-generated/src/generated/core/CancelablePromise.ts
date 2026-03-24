/* generated override for Angular compatibility */
export class CancelError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CancelError';
  }
  public get isCancelled(): boolean { return true; }
}
export interface OnCancel {
  readonly isResolved: boolean;
  readonly isRejected: boolean;
  readonly isCancelled: boolean;
  (cancelHandler: () => void): void;
}
export class CancelablePromise<T> implements Promise<T> {
  private isResolvedFlag = false;
  private isRejectedFlag = false;
  private isCancelledFlag = false;
  private cancelHandlers: Array<() => void> = [];
  private readonly promise: Promise<T>;
  constructor(executor: (resolve: (value: T | PromiseLike<T>) => void, reject: (reason?: unknown) => void, onCancel: OnCancel) => void) {
    this.promise = new Promise<T>((resolve, reject) => {
      const onResolve = (value: T | PromiseLike<T>): void => {
        if (this.isResolvedFlag || this.isRejectedFlag || this.isCancelledFlag) return;
        this.isResolvedFlag = true;
        resolve(value);
      };
      const onReject = (reason?: unknown): void => {
        if (this.isResolvedFlag || this.isRejectedFlag || this.isCancelledFlag) return;
        this.isRejectedFlag = true;
        reject(reason);
      };
      const onCancel = ((cancelHandler: () => void): void => {
        if (this.isResolvedFlag || this.isRejectedFlag || this.isCancelledFlag) return;
        this.cancelHandlers.push(cancelHandler);
      }) as OnCancel;
      Object.defineProperty(onCancel, 'isResolved', { get: () => this.isResolvedFlag });
      Object.defineProperty(onCancel, 'isRejected', { get: () => this.isRejectedFlag });
      Object.defineProperty(onCancel, 'isCancelled', { get: () => this.isCancelledFlag });
      executor(onResolve, onReject, onCancel);
    });
  }
  get [Symbol.toStringTag](): string { return 'Cancellable Promise'; }
  public then<TResult1 = T, TResult2 = never>(onFulfilled?: ((value: T) => TResult1 | PromiseLike<TResult1>) | null, onRejected?: ((reason: unknown) => TResult2 | PromiseLike<TResult2>) | null): Promise<TResult1 | TResult2> {
    return this.promise.then(onFulfilled ?? undefined, onRejected ?? undefined);
  }
  public catch<TResult = never>(onRejected?: ((reason: unknown) => TResult | PromiseLike<TResult>) | null): Promise<T | TResult> {
    return this.promise.catch(onRejected ?? undefined);
  }
  public finally(onFinally?: (() => void) | null): Promise<T> {
    return this.promise.finally(onFinally ?? undefined);
  }
  public cancel(): void {
    if (this.isResolvedFlag || this.isRejectedFlag || this.isCancelledFlag) return;
    this.isCancelledFlag = true;
    for (const cancelHandler of this.cancelHandlers) cancelHandler();
    this.cancelHandlers = [];
  }
}
