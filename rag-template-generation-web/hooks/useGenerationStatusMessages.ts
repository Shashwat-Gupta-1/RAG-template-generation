import { useState, useEffect, useRef } from "react";

const MESSAGES = [
  "Creating your image...",
  "Sketching it out...",
  "Drafting the composition...",
  "Setting the scene...",
  "Polishing details...",
  "Adding final touches...",
  "Almost there...",
];

// The last 3 messages to cycle if generation takes a long time
const LOOP_START_INDEX = 4; // "Polishing details..."

export type GenerationStatus = "idle" | "generating" | "success" | "error";

export function useGenerationStatusMessages(status: GenerationStatus) {
  const [currentMessage, setCurrentMessage] = useState("");
  
  // A ref to keep track of the current index without depending on it in useEffect
  const indexRef = useRef(0);

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;

    if (status === "generating") {
      // Start with the first message immediately
      if (indexRef.current === 0) {
        setCurrentMessage(MESSAGES[0]);
      }

      const cycleMessage = () => {
        const nextIndex = indexRef.current + 1;
        
        if (nextIndex < MESSAGES.length) {
          indexRef.current = nextIndex;
        } else {
          // Loop back to the final stages
          indexRef.current = LOOP_START_INDEX;
        }
        
        setCurrentMessage(MESSAGES[indexRef.current]);

        // Random jitter between 4s and 6s
        const jitterMs = Math.floor(Math.random() * 2000) + 4000;
        timeoutId = setTimeout(cycleMessage, jitterMs);
      };

      // Set the first timer
      const initialJitterMs = Math.floor(Math.random() * 2000) + 4000;
      timeoutId = setTimeout(cycleMessage, initialJitterMs);
      
    } else if (status === "success") {
      setCurrentMessage("Finishing up...");
    } else if (status === "error") {
      setCurrentMessage("Something went wrong — please try again.");
      indexRef.current = 0;
    } else {
      // idle
      setCurrentMessage("");
      indexRef.current = 0;
    }

    return () => {
      clearTimeout(timeoutId);
    };
  }, [status]);

  return { currentMessage };
}
