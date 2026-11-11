export const PLAYBACK_LABELS = Object.freeze({
  play: "Reproducir",
  pause: "Pausar",
  next: "Paso siguiente",
  prev: "Paso anterior",
  reset: "Reiniciar",
});

const DEFAULT_INTERVAL_MS = 500;

export function createPlayback(
  steps,
  {
    intervalMs = DEFAULT_INTERVAL_MS,
    schedule = setInterval,
    cancel = clearInterval,
    reducedMotion = false,
    onStep = () => {},
  } = {},
) {
  const trace = Array.isArray(steps) ? steps : [];
  let status = "idle";
  let index = -1;
  let timerHandle = null;
  let timerActive = false;

  function activeStep() {
    return index >= 0 && index < trace.length ? trace[index] : null;
  }

  function snapshot() {
    return {
      status,
      index,
      activeStep: activeStep(),
      canPrev: index > 0,
      canNext: trace.length > 0 && index < trace.length - 1,
      total: trace.length,
    };
  }

  function emit() {
    onStep(activeStep(), snapshot());
  }

  function stopTimer() {
    if (!timerActive) {
      return;
    }
    cancel(timerHandle);
    timerHandle = null;
    timerActive = false;
  }

  function finish() {
    stopTimer();
    status = "finished";
    emit();
  }

  function advance() {
    if (index >= trace.length - 1) {
      finish();
      return;
    }
    index += 1;
    if (index >= trace.length - 1) {
      finish();
      return;
    }
    emit();
  }

  function play() {
    if (trace.length === 0) {
      stopTimer();
      index = -1;
      status = "finished";
      emit();
      return;
    }

    if (reducedMotion) {
      stopTimer();
      index = trace.length - 1;
      status = "finished";
      emit();
      return;
    }

    if (status === "playing") {
      return;
    }

    if (trace.length === 1) {
      stopTimer();
      index = 0;
      status = "finished";
      emit();
      return;
    }

    if (status === "finished" || index < 0 || index >= trace.length - 1) {
      index = 0;
    }
    status = "playing";
    emit();

    timerHandle = schedule(advance, intervalMs);
    timerActive = true;
  }

  function pause() {
    if (status !== "playing") {
      return;
    }
    stopTimer();
    status = "paused";
    emit();
  }

  function next() {
    if (trace.length === 0) {
      index = -1;
      status = "finished";
      emit();
      return;
    }
    if (index >= trace.length - 1) {
      return;
    }
    stopTimer();
    index += 1;
    status = index >= trace.length - 1 ? "finished" : "paused";
    emit();
  }

  function prev() {
    if (index <= 0) {
      return;
    }
    stopTimer();
    index -= 1;
    status = "paused";
    emit();
  }

  function reset() {
    stopTimer();
    index = -1;
    status = "idle";
    emit();
  }

  return {
    play,
    pause,
    next,
    prev,
    reset,
    getState: snapshot,
  };
}
