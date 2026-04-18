/**
 * Wrapper qui marque un bloc comme éditable.
 * En mode édition (Alt+E), bordure pointillée + nom du bloc affiché.
 * V2 : devient un bloc draggable + resizable.
 */
export function Editable({
  name,
  className = "",
  children,
}: {
  name: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div data-editable="true" data-block-name={name} className={className}>
      {children}
    </div>
  );
}
