"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuthStore } from "@/stores/use-auth-store";
import { ApiError, apiRequest } from "@/lib/api-client";

// Setup Data Type
interface SetupData {
  secret: string;
  qr_code: string;
}

interface TwoFactorStatus {
  is_enabled: boolean;
}

function requestError(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

// 2FA Hook
export function use2FA() {
  const token =
    useAuthStore((s) => s.token) ??
    (typeof window !== "undefined" ? localStorage.getItem("access_token") : null);

  const [isEnabled, setIsEnabled] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isVerifying, setIsVerifying] = useState(false);
  const [showSetup, setShowSetup] = useState(false);
  const [showDisable, setShowDisable] = useState(false);
  const [setupData, setSetupData] = useState<SetupData | null>(null);
  const [verificationCode, setVerificationCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [error, setError] = useState("");

  // Fetch 2FA Status When Mount
  useEffect(() => {
    if (!token) {
      const timeoutId = window.setTimeout(() => setIsLoading(false), 0);
      return () => window.clearTimeout(timeoutId);
    }

    (async () => {
      try {
        const data = await apiRequest<TwoFactorStatus>("/auth/2fa/status", {
          token,
        });
        setIsEnabled(data.is_enabled);
      } catch (error) {
        setError(requestError(error, "Không thể kết nối server"));
      } finally {
        setIsLoading(false);
      }
    })();
  }, [token]);

  // Toggle
  const handleToggle = useCallback(
    async (checked: boolean) => {
      setError("");

      if (checked && !isEnabled) {
        // Setup
        setIsLoading(true);
        try {
          const data = await apiRequest<SetupData>("/auth/2fa/setup", {
            method: "POST",
            token,
          });
          setSetupData(data);
          setShowSetup(true);
        } catch (error) {
          setError(requestError(error, "Không thể thiết lập 2FA"));
        } finally {
          setIsLoading(false);
        }
      } else if (!checked && isEnabled) {
        setShowDisable(true);
      }
    },
    [isEnabled, token],
  );

  // Verify
  const handleVerify = useCallback(async () => {
    setIsVerifying(true);
    setError("");

    try {
      await apiRequest<unknown>("/auth/2fa/verify", {
        method: "POST",
        token,
        body: { totp_code: verificationCode },
      });
      setIsEnabled(true);
      setShowSetup(false);
      setSetupData(null);
      setVerificationCode("");
    } catch (error) {
      setError(requestError(error, "Mã xác thực không đúng"));
    } finally {
      setIsVerifying(false);
    }
  }, [verificationCode, token]);

  // Disable
  const handleDisable = useCallback(async () => {
    setIsVerifying(true);
    setError("");

    try {
      await apiRequest<unknown>("/auth/2fa/disable", {
        method: "POST",
        token,
        body: { totp_code: disableCode },
      });
      setIsEnabled(false);
      setShowDisable(false);
      setDisableCode("");
    } catch (error) {
      setError(requestError(error, "Mã xác thực không đúng"));
    } finally {
      setIsVerifying(false);
    }
  }, [disableCode, token]);

  // Cancel Setup
  const handleCancelSetup = useCallback(() => {
    setShowSetup(false);
    setSetupData(null);
    setVerificationCode("");
    setError("");
  }, []);

  // Cancel Disable
  const handleCancelDisable = useCallback(() => {
    setShowDisable(false);
    setDisableCode("");
    setError("");
  }, []);

  // Return
  return {
    isEnabled,
    isLoading,
    isVerifying,
    showSetup,
    showDisable,
    setupData,
    verificationCode,
    disableCode,
    error,
    setVerificationCode,
    setDisableCode,
    handleToggle,
    handleVerify,
    handleDisable,
    handleCancelSetup,
    handleCancelDisable,
  };
}
