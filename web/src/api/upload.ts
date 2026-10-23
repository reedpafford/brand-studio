import { api, errorText } from "./client";

/** Upload one file to the server and return its stored record. Throws a plain-language error. */
export async function uploadFile(file: File) {
  const { data, error } = await api.POST("/files", {
    body: { upload: file as unknown as string },
    bodySerializer: () => {
      const form = new FormData();
      form.append("upload", file);
      return form;
    },
  });
  if (!data) throw new Error(errorText(error));
  return data;
}

export const fileUrl = (id: number) => `/api/files/${id}`;
