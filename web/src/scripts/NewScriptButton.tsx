import { useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileInput, FileText, Music, Plus } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorText } from "../api/client";
import { Button, Menu, MenuItem, buttonClass } from "../components";
import { errorText as errorClass } from "../ui";

export const UNTITLED = "Untitled script";

/** New script: Story or Song first (song ads, flows S1), then one press makes the draft and opens its first step (rename it there). */
export function NewScriptButton({ brandId }: { brandId: number }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const pressed = useRef(false); // set at once, before a re-render, so a fast double tap makes one draft
  const make = useMutation({
    mutationFn: async (kind: "story" | "song") => {
      const { data, error } = await api.POST("/scripts", { body: { brand_id: brandId, title: UNTITLED, description: "", notes: "", reference_replace: "", text: "", kind } });
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
  const choice = (kind: "story" | "song", Icon: typeof FileText, title: string, about: string, close: () => void) => (
    <MenuItem
      onClick={() => {
        close();
        if (pressed.current) return;
        pressed.current = true;
        make.mutate(kind);
      }}
    >
      <Icon size={20} strokeWidth={1.75} aria-hidden />
      <span className="flex-1 py-2">
        <span className="block font-medium">{title}</span>
        <span className="block text-sm text-muted">{about}</span>
      </span>
    </MenuItem>
  );
  return (
    <>
      <Menu
        title="New script"
        align="right"
        trigger={(p) => (
          <Button icon={Plus} busy={make.isPending} {...p}>
            New script
          </Button>
        )}
      >
        {(close) => (
          <>
            {choice("story", FileText, "Story", "Dialogue and action, as today.", close)}
            {choice("song", Music, "Song", "Your lyrics, sung word for word over a music video.", close)}
          </>
        )}
      </Menu>
      {make.isError && <p role="alert" className={errorClass}>{make.error.message} Press New script to try again.</p>}
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
