"use client";

import { useRef, useState } from "react";

export type DropzoneProps = {
  accept: string;
  multiple?: boolean;
  onFiles: (files: File[]) => void;
  selectedLabel?: string | null;
  hint: string;
  idle: string;
};

export function Dropzone({ accept, multiple = false, onFiles, selectedLabel, hint, idle }: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  function emit(list: FileList | null) {
    const files = Array.from(list ?? []);
    if (files.length > 0) onFiles(files);
  }

  return (
    <button
      type="button"
      className={`dropzone${dragOver ? " dragover" : ""}`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        emit(e.dataTransfer.files);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        className="dropzone-input"
        onChange={(e) => emit(e.target.files)}
      />
      <span className="dropzone-title">{selectedLabel ? selectedLabel : idle}</span>
      <span className="dropzone-hint">{hint}</span>
    </button>
  );
}
