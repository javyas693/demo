import { ProgramWorkspaceClient } from "./client-page"

export default function Page({ params }: { params: { programKey: string } }) {
    return <ProgramWorkspaceClient programKey={params.programKey} />;
}
