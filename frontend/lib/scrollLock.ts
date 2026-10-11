let lockCount = 0;

/** Lock body scroll. Call the returned function to release. Overflow is cleared only by the last release. */
export function lockBodyScroll(): () => void {
  if (typeof document === "undefined") return () => {};
  lockCount += 1;
  document.body.style.overflow = "hidden";
  let released = false;
  return () => {
    if (released) return;
    released = true;
    lockCount = Math.max(0, lockCount - 1);
    if (lockCount === 0) {
      document.body.style.overflow = "";
    }
  };
}
