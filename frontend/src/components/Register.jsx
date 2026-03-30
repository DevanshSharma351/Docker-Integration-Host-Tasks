import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { CircleAlert, CircleCheck } from 'lucide-react';


function parseRegisterError(err) {
  if (!err) return 'Registration failed';
  if (typeof err === 'string') return err;
  if (err.detail) return err.detail;

  const firstEntry = Object.entries(err)[0];
  if (firstEntry && Array.isArray(firstEntry[1]) && firstEntry[1].length) {
    return `${firstEntry[0]}: ${firstEntry[1][0]}`;
  }

  return 'Registration failed';
}

export default function Register() {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    role: 'viewer',
    first_name: '',
    last_name: '',
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await register(formData);
      setSuccess(true);
    } catch (err) {
      setError(parseRegisterError(err));
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="rounded-lg border border-emerald-200 bg-emerald-50/70 p-4 dark:border-emerald-500/40 dark:bg-emerald-500/10">
        <div className="flex items-center gap-3 text-emerald-700 dark:text-emerald-300">
          <CircleCheck className="size-6" />
          <div>
            <h2 className="text-lg font-semibold">Registration Successful</h2>
            <p className="text-sm mt-1">You can now login with your new credentials.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      {error && (
        <Alert variant="destructive" className="mb-4">
          <CircleAlert className="size-4" />
          <AlertTitle>Registration Failed</AlertTitle>
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
              name="username"
              value={formData.username}
              onChange={handleChange}
              required
            />
          </Field>

          <Field>
            <FieldLabel htmlFor="email">Email</FieldLabel>
            <Input
              id="email"
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
            />
            <FieldDescription>We will only use this for account communication.</FieldDescription>
          </Field>

          <Field>
            <FieldLabel htmlFor="password">Password (min 8 chars)</FieldLabel>
            <Input
              id="password"
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              minLength={8}
            />
          </Field>

          <Field>
            <FieldLabel>Role</FieldLabel>
            <Select
              value={formData.role}
              onValueChange={(value) => setFormData((prev) => ({ ...prev, role: value }))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="viewer">Viewer</SelectItem>
                <SelectItem value="host">Host</SelectItem>
                <SelectItem value="admin">Admin</SelectItem>
              </SelectContent>
            </Select>
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="first_name">First Name</FieldLabel>
              <Input
                id="first_name"
                type="text"
                name="first_name"
                value={formData.first_name}
                onChange={handleChange}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="last_name">Last Name</FieldLabel>
              <Input
                id="last_name"
                type="text"
                name="last_name"
                value={formData.last_name}
                onChange={handleChange}
              />
            </Field>
          </div>

          <Field>
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? 'Creating Account...' : 'Register'}
            </Button>
          </Field>
        </FieldGroup>
      </form>
    </div>
  );
}
