import { useMemo, useState } from 'react';
import { Search, Rocket } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';

export default function ImageGallery({ images = [], isLoading = false, error = '', onRefresh, onDeploy }) {
  const [query, setQuery] = useState('');

  const filteredImages = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return images;

    return images.filter((image) => {
      const ref = image.image_ref?.toLowerCase() || '';
      const source = image.source?.toLowerCase() || '';
      return ref.includes(normalized) || source.includes(normalized);
    });
  }, [images, query]);

  return (
    <Card className="border-border/70 bg-card/95">
      <CardHeader className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-xl">Image Gallery</CardTitle>
            <CardDescription>Browse available host images and deploy one to a new container.</CardDescription>
          </div>
          <Button variant="outline" onClick={onRefresh} disabled={isLoading}>
            {isLoading ? 'Refreshing...' : 'Refresh'}
          </Button>
        </div>

        <div className="relative max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-9"
            placeholder="Search by image reference"
            aria-label="Search images"
          />
        </div>
      </CardHeader>

      <CardContent>
        {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}

        {filteredImages.length === 0 ? (
          <div className="rounded-xl border border-dashed p-8 text-center">
            <p className="text-sm text-muted-foreground">
              {query ? 'No images match your search.' : 'No images available yet.'}
            </p>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {filteredImages.map((image) => (
              <div key={image.image_ref} className="rounded-xl border bg-background/40 p-4">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-semibold break-all">{image.image_ref}</p>
                  <Badge variant="secondary" className="uppercase">{image.status || 'ready'}</Badge>
                </div>

                <p className="mt-2 text-xs text-muted-foreground">
                  Source: {image.source || 'local host'}
                </p>

                <Button
                  className="mt-4 w-full"
                  onClick={() => onDeploy?.(image.image_ref)}
                >
                  <Rocket className="size-4" />
                  Deploy
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
