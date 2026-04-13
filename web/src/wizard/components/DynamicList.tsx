import type { ReactNode } from "react";
import { Plus, Trash2 } from "lucide-react";

interface DynamicListProps<T> {
  items: T[];
  onAdd: () => void;
  onRemove: (index: number) => void;
  renderItem: (item: T, index: number) => ReactNode;
  addLabel: string;
  emptyMessage: string;
  itemLabel: (item: T) => string;
}

export default function DynamicList<T>({
  items,
  onAdd,
  onRemove,
  renderItem,
  addLabel,
  emptyMessage,
  itemLabel,
}: DynamicListProps<T>) {
  return (
    <div className="space-y-4">
      {items.length === 0 && (
        <p className="text-sm text-gray-500 dark:text-gray-500 text-center py-4">{emptyMessage}</p>
      )}

      {items.map((item, i) => (
        <div key={i} className="relative rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-4">
          <button
            type="button"
            onClick={() => onRemove(i)}
            aria-label={`Remove ${itemLabel(item)}`}
            className="absolute top-3 right-3 p-1 rounded text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950 transition-colors"
          >
            <Trash2 size={16} />
          </button>
          {renderItem(item, i)}
        </div>
      ))}

      <button
        type="button"
        onClick={onAdd}
        className="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
      >
        <Plus size={16} />
        {addLabel}
      </button>
    </div>
  );
}
