/** Make the user retype a monitor's name before it is deleted. */
export function confirmDelete(name: string): boolean {
  const typed = window.prompt(
    `This deletes "${name}" and all its check history.\n\nType the name to confirm:`,
  );
  if (typed === null) return false;
  if (typed.trim() !== name) {
    window.alert("Name didn't match. Nothing was deleted.");
    return false;
  }
  return true;
}
