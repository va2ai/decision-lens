import { useMutation } from "@tanstack/react-query";
import { analyze } from "../lib/api";

export function useAnalyze() {
  return useMutation({ mutationFn: analyze });
}
