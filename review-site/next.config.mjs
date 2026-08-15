/** @type {import('next').NextConfig} */
const nextConfig = {
  // Scans are served through the authenticated /api/scan proxy;
  // no remote image domains needed.
  //
  // lib/data.ts reads data/<id>.json with fs at request time through a
  // dynamic path, which Vercel's static file tracer cannot see — declare
  // the files explicitly or the deployed lambdas ship without them.
  outputFileTracingIncludes: {
    "/*": ["./data/*.json"],
  },
};

export default nextConfig;
