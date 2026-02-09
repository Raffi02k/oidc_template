import { type Configuration, type PopupRequest, type SilentRequest } from "@azure/msal-browser";

export const msalConfig: Configuration = {
    auth: {
        clientId: import.meta.env.VITE_ENTRA_CLIENT_ID || "YOUR_CLIENT_ID",
        authority: `https://login.microsoftonline.com/${import.meta.env.VITE_ENTRA_TENANT_ID || "YOUR_TENANT_ID"}`,
        redirectUri: window.location.origin,
        postLogoutRedirectUri: window.location.origin,
    },
    cache: {
        cacheLocation: "sessionStorage",
        storeAuthStateInCookie: false,
    },
};

export const loginRequest: PopupRequest = {
    scopes: ["openid", "profile", "User.Read"],
    prompt: "select_account",
};

const apiScope = import.meta.env.VITE_ENTRA_API_SCOPE;

export const apiTokenRequest: SilentRequest = {
    // Access token for your API scope (not Graph)
    scopes: apiScope ? [apiScope] : [],
};
