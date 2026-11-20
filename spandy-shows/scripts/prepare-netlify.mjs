import {writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

export function netlifyRoutes(value){
 if(!value)throw new Error('Set SPANDY_API_ORIGIN to the hosted execution backend HTTPS origin before deploying. Netlify alone does not run the compiler service.');
 let url;
 try{url=new URL(value)}catch{throw new Error('SPANDY_API_ORIGIN must be a valid HTTPS origin.')}
 if(url.protocol!=='https:'||url.username||url.password||url.pathname!=='/'||url.search||url.hash)
  throw new Error('SPANDY_API_ORIGIN must be an HTTPS origin without credentials, paths, query parameters or fragments.');
 if(['localhost','127.0.0.1','[::1]'].includes(url.hostname)||url.hostname.endsWith('.localhost')||url.hostname.endsWith('.local'))
  throw new Error('SPANDY_API_ORIGIN must be hosted online; the local preview is not reachable from Netlify.');
 // Keep API requests ahead of the SPA fallback. Every operation is a short
 // request; execution and input waits continue independently in the backend.
 return `/api/* ${url.origin}/api/:splat 200!\n/* /index.html 200\n`;
}

if(process.argv[1]&&pathToFileURL(resolve(process.argv[1])).href===import.meta.url){
 const routes=netlifyRoutes(process.env.SPANDY_API_ORIGIN);
 await writeFile(fileURLToPath(new URL('../public/_redirects',import.meta.url)),routes);
 console.log('Netlify API proxy and application routes prepared.');
}
