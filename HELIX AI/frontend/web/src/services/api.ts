
interface ChatResponse {
   type: 'chat' | 'intervention';
   risk_level: string;
   response: string | any;
   metadata?: {
      emotion?: any;
   }
}

const API_BASE_URL = 'https://helix-ai-backend-new-1.onrender.com';

export const apiService = {
   async login(email: string, password: string) {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
         const error = await response.json();
         throw new Error(error.detail || 'Login failed');
      }
      return await response.json();
   },

   async register(email: string, password: string, full_name: string) {
      const response = await fetch(`${API_BASE_URL}/auth/register`, {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({ email, password, full_name }),
      });
      if (!response.ok) {
         const error = await response.json();
         throw new Error(error.detail || 'Registration failed');
      }
      return await response.json();
   },

   async sendMessage(message: string, userId: string = 'default_user', sessionId?: number): Promise<ChatResponse> {
      const response = await fetch(`${API_BASE_URL}/chat/`, {
         method: 'POST',
         headers: {
            'Content-Type': 'application/json',
         },
         body: JSON.stringify({ message, user_id: parseInt(userId) || 0, session_id: sessionId }),
      });

      if (!response.ok) {
         throw new Error(`API Error: ${response.statusText}`);
      }

      return await response.json();
   }
};
