import { useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileInput, Plus } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorText } from "../api/client";
import { Button, buttonClass } from "../components";
import { errorText as errorClass } from "../ui";

export const UNTITLED = "Untitled script";

/** New script: one press makes the draft and opens the Script screen (rename it there). */
export function NewScriptButton({ brandId }: { brandId: number }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const pressed = useRef(false); // set at once, before a re-render, so a fast double tap makes one draft
  const make = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/scripts", { body: { brand_id: brandId, title: UNTITLED, description: "", notes: "", reference_replace: "", text: "" } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (made) => {
      await queryClient.invalidateQueries({ queryKey: ["scripts"] });
      navigate(`/b/${brandId}/scripts/${made.id}`);
    },
    onError: () => {
      pressed.current = false;
    },
  });
  return (
    <>
      <Button icon={Plus} busy={make.isPending} onClick={() => {
          if (pressed.current) return;
          pressed.current = true;
          make.mutate();
        }}>
        New script
      </Button>
      {make.isError && <p role="alert" className={errorClass}>{make.error.message}</p>}
    </>
  );
}

/** Import a reel starts from a link or a video, not words, so it keeps its own page. */
export function ImportReelLink({ brandId }: { brandId: number }) {
  return (
    <Link to={`/b/${brandId}/scripts/import`} className={buttonClass("secondary")}>
      <FileInput size={20} strokeWidth={1.75} aria-hidden />
      Import a reel
    </Link>
  );
}
