class ProviderError(RuntimeError):
    code = "provider_error"
    public_message = "Dịch vụ AI tạm thời gặp lỗi. Vui lòng thử lại sau."

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(self.public_message)


class ProviderAuthenticationError(ProviderError):
    code = "provider_authentication"
    public_message = "Dịch vụ AI chưa được cấu hình xác thực hợp lệ."


class ProviderTimeoutError(ProviderError):
    code = "provider_timeout"
    public_message = "Dịch vụ AI phản hồi quá chậm. Vui lòng thử lại."


class ProviderRateLimitError(ProviderError):
    code = "provider_rate_limit"
    public_message = "Dịch vụ AI đang quá tải. Vui lòng thử lại sau."


class ProviderUnavailableError(ProviderError):
    code = "provider_unavailable"
    public_message = "Dịch vụ AI hiện không khả dụng. Vui lòng thử lại sau."
