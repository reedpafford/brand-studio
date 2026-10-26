import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, errorText } from "../api/client";
import { Button, Field, Panel } from "../components";
import { useToast } from "../toast";

/** Reed's "＋ New brand": a name, then the new brand opens on its Look page to add the logo and colours. */
export function NewBrand({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const make = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/brands", { body: { name: name.trim(), colours: [], fonts: [], tone_notes: "", never_say: [], legal_line: "", end_line: "" } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (brand) => {
      await Promise.all([queryClient.invalidateQueries({ queryKey: ["brands"] }), queryClient.invalidateQueries({ queryKey: ["usage"] })]);
      onClose();
      navigate(`/b/${brand.id}/brand`);
      toast(`${brand.name} is ready. Add its logo and colours.`);
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (name.trim()) make.mutate();
  };
  return (
    <Panel title="New brand" onClose={onClose}>
      <form className="space-y-4" onSubmit={submit}>
        <Field label="Brand name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} autoFocus hint="You add its logo, colours and screens next." error={make.isError ? make.error.message : null} />
        <Button type="submit" busy={make.isPending} disabled={!name.trim()} reason={!name.trim() ? "Give it a name first" : undefined} className="w-full">
          Create brand
        </Button>
      </form>
    </Panel>
  );
}
