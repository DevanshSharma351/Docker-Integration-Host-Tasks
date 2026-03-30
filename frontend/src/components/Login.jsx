import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { CircleAlert } from 'lucide-react';


function parseLoginError(err) {
  if (!err) return 'Login failed';
  if (typeof err === 'string') return err;
  if (err.detail) return err.detail;
  if (Array.isArray(err.non_field_errors) && err.non_field_errors.length) {
    return err.non_field_errors[0];
  }
  return 'Login failed';
}

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
    } catch (err) {
      setError(parseLoginError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {error && (
        <Alert variant="destructive" className="mb-4">
          <CircleAlert className="size-4" />
          <AlertTitle>Login Failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={handleSubmit}>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="username">Username</FieldLabel>
            <Input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </Field>

          <Field>
            <FieldLabel htmlFor="password">Password</FieldLabel>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </Field>

          <Field>
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? 'Signing In...' : 'Login'}
            </Button>
          </Field>
        </FieldGroup>
      </form>

      <FieldDescription className="mt-4 text-center">
        Demo user: <strong>dhee</strong> / <strong>Dhee@12345</strong>
      </FieldDescription>
    </div>
  );
}
