import { render, screen } from "@testing-library/react";
import { Badge, Empty, ErrorBox, Stat } from "../components/ui";

test("ui primitives render", () => {
  render(<><Stat label="Total" value={42} /><Empty title="Nothing here" /><ErrorBox msg="Boom" /><Badge>vip</Badge></>);
  expect(screen.getByText("42")).toBeInTheDocument();
  expect(screen.getByText("Nothing here")).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("Boom");
  expect(screen.getByText("vip")).toBeInTheDocument();
});
