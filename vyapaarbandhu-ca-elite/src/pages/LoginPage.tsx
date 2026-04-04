import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';

const LoginPage = () => {
  const { login, signup } = useAuth();
  const { toast } = useToast();

  const [mode,    setMode]    = useState<'login' | 'signup'>('login');
  const [loading, setLoading] = useState(false);

  // Login fields
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');

  // Signup fields
  const [name,  setName]  = useState('');
  const [phone, setPhone] = useState('');

  const handleLogin = async () => {
    if (!email || !password) {
      toast({ title: 'Missing fields', description: 'Enter email and password.', variant: 'destructive' });
      return;
    }
    setLoading(true);
    const result = await login(email, password);
    setLoading(false);
    if (!result.success) {
      toast({ title: 'Login failed', description: result.error, variant: 'destructive' });
    }
  };

  const handleSignup = async () => {
    if (!name || !email || !password) {
      toast({ title: 'Missing fields', description: 'Name, email and password are required.', variant: 'destructive' });
      return;
    }
    if (password.length < 6) {
      toast({ title: 'Weak password', description: 'Password must be at least 6 characters.', variant: 'destructive' });
      return;
    }
    setLoading(true);
    const result = await signup(name, email, password, phone || undefined);
    setLoading(false);
    if (!result.success) {
      toast({ title: 'Signup failed', description: result.error, variant: 'destructive' });
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') mode === 'login' ? handleLogin() : handleSignup();
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] flex items-center justify-center px-4">
      <div className="w-full max-w-md">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-xl bg-blue-600 flex items-center justify-center text-white font-bold text-2xl mx-auto mb-4">
            VB
          </div>
          <h1 className="text-2xl font-bold text-gray-900">VyapaarBandhu</h1>
          <p className="text-sm text-gray-600 mt-1">CA Portal - GST Compliance Platform</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">

          {/* Tab toggle */}
          <div className="flex gap-1 mb-6 p-1 rounded-lg bg-gray-100">
            <button
              onClick={() => setMode('login')}
              className={cn(
                'flex-1 py-2 rounded-md text-sm font-medium transition-all duration-200',
                mode === 'login'
                  ? 'bg-white text-gray-900 shadow-sm border border-gray-200'
                  : 'text-gray-600 hover:text-gray-900'
              )}
            >
              Login
            </button>
            <button
              onClick={() => setMode('signup')}
              className={cn(
                'flex-1 py-2 rounded-md text-sm font-medium transition-all duration-200',
                mode === 'signup'
                  ? 'bg-white text-gray-900 shadow-sm border border-gray-200'
                  : 'text-gray-600 hover:text-gray-900'
              )}
            >
              Create Account
            </button>
          </div>

          {/* Fields */}
          <div className="space-y-3" onKeyDown={handleKeyDown}>

            {mode === 'signup' && (
              <>
                <div>
                  <label className="text-xs text-gray-600 mb-1 block">Full Name *</label>
                  <Input
                    placeholder="CA Rajesh Sharma"
                    value={name}
                    onChange={e => setName(e.target.value)}
                    className="bg-white border-gray-200 text-gray-900 rounded-lg"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-600 mb-1 block">Phone (optional)</label>
                  <Input
                    placeholder="+91 9876543210"
                    value={phone}
                    onChange={e => setPhone(e.target.value)}
                    className="bg-white border-gray-200 text-gray-900 rounded-lg"
                  />
                </div>
              </>
            )}

            <div>
              <label className="text-xs text-gray-600 mb-1 block">Email *</label>
              <Input
                type="email"
                placeholder="ca@example.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="bg-white border-gray-200 text-gray-900 rounded-lg"
              />
            </div>

            <div>
              <label className="text-xs text-gray-600 mb-1 block">Password *</label>
              <Input
                type="password"
                placeholder={mode === 'signup' ? 'Min 6 characters' : '•••••••••'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="bg-white border-gray-200 text-gray-900 rounded-lg"
              />
            </div>
          </div>

          {/* Submit */}
          <Button
            variant="indigo"
            className="w-full mt-5 rounded-lg"
            disabled={loading}
            onClick={mode === 'login' ? handleLogin : handleSignup}
          >
            {loading
              ? (mode === 'login' ? 'Logging in...' : 'Creating account...')
              : (mode === 'login' ? 'Login →' : 'Create Account →')
            }
          </Button>

          {/* Toggle hint */}
          <p className="text-center text-xs text-gray-600 mt-4">
            {mode === 'login'
              ? <>New CA? <button onClick={() => setMode('signup')} className="text-blue-600 hover:underline font-medium">Create an account</button></>
              : <>Already registered? <button onClick={() => setMode('login')} className="text-blue-600 hover:underline font-medium">Login here</button></>
            }
          </p>
        </div>

        {/* Footer */}
        <div className="text-center mt-6 space-y-1">
          <p className="text-xs text-gray-600">
            🤝 Serving 8 crore Indian SMEs
          </p>
          <p className="text-xs text-gray-600">
            Built for OceanLab X CHARUSAT Hacks 2026
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
