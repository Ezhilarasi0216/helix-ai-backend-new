/**
 * Dynamic API Configuration
 * 
 * This ensures the frontend can connect to the backend regardless of which 
 * device or IP address is being used on the network.
 */

// Detect if we are running in development or production
const isDevelopment = import.meta.env.MODE === 'development';

// Get the current hostname (e.g., localhost, 192.168.1.5, or healix.ai)
const hostname = typeof window !== 'undefined' ? window.location.hostname : 'localhost';

// Backend always runs on Render
export const BACKEND_PORT = '10000';

// Construct the base API URL
// If accessed via fixed IP on a network, it will use that IP.
// If accessed via localhost, it uses localhost.
export const API_BASE_URL = `https://helix-ai-backend-new-1.onrender.com`;

// Function to get full URL with prefix
export const getApiUrl = (path: string): string => {
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    return `${API_BASE_URL}${cleanPath}`;
};

export default {
    API_BASE_URL,
    getApiUrl
};
