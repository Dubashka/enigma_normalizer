import { useState } from 'react';
import { uploadFile as apiUploadFile } from '../api/normalization';
import type { UploadResponse } from '../types/sheet';

interface FileUploadState {
  filename: string | null;
  sheetsData: UploadResponse['sheets'];
  isCsv: boolean;
  isLoading: boolean;
  error: string | null;
}

const INITIAL_STATE: FileUploadState = {
  filename: null,
  sheetsData: {},
  isCsv: false,
  isLoading: false,
  error: null,
};

export function useFileUpload() {
  const [state, setState] = useState<FileUploadState>(INITIAL_STATE);

  async function uploadFile(file: File) {
    setState(s => ({ ...s, isLoading: true, error: null }));
    try {
      const res = await apiUploadFile(file);
      setState({
        filename: res.filename,
        sheetsData: res.sheets,
        isCsv: res.is_csv,
        isLoading: false,
        error: null,
      });
    } catch (e) {
      setState(s => ({ ...s, isLoading: false, error: (e as Error).message }));
    }
  }

  function reset() {
    setState(INITIAL_STATE);
  }

  return { ...state, uploadFile, reset };
}
